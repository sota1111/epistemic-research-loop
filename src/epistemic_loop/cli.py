from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import typer
import yaml

from epistemic_loop.adapters.executor.ai_dev_control_plane import AiDevControlPlaneAdapter
from epistemic_loop.adapters.executor.base import ExecutorAdapter, result_path
from epistemic_loop.adapters.executor.local import LocalExecutor
from epistemic_loop.adapters.kaggle import (
    KaggleCliSubmissionAdapter,
    SubmissionCandidate,
    SubmissionLedger,
    fingerprint,
    plan_submission,
)
from epistemic_loop.adapters.kaggle.manual import manual_submission_packet, write_manual_packet
from epistemic_loop.adapters.llm.base import StructuredLlm
from epistemic_loop.agents.auto import AutomaticProposer
from epistemic_loop.agents.belief_interpreter import DISPOSITION_STATUS, interpret_evidence
from epistemic_loop.agents.falsifier import Falsifier
from epistemic_loop.agents.observer import CompetitionObserver
from epistemic_loop.agents.proposal_bridge import ProposalBridge
from epistemic_loop.belief.updater import belief_update
from epistemic_loop.benchmark.evaluator import finalize_benchmark
from epistemic_loop.benchmark.paired_runner import run_synthetic_plan
from epistemic_loop.benchmark.protocol import BenchmarkPlan, load_plan, save_plan
from epistemic_loop.config import AppConfig, load_config
from epistemic_loop.controller.autoloop import AutonomousLoop, LoopSettings
from epistemic_loop.controller.budget_manager import BudgetManager
from epistemic_loop.controller.phase_policy import PhaseEvidence
from epistemic_loop.controller.research_graph import (
    LoopStateError,
    ResearchController,
    fingerprint_path,
)
from epistemic_loop.controller.run_state import RunState
from epistemic_loop.domain.enums import HypothesisStatus, Phase, VerifierResult
from epistemic_loop.domain.events import EventType
from epistemic_loop.domain.models import (
    CompetitionWorldModel,
    ExperimentProposal,
    ExperimentResult,
    Hypothesis,
)
from epistemic_loop.holdout.leaderboard import LeaderboardGate
from epistemic_loop.holdout.query_ledger import QueryLedger
from epistemic_loop.holdout.sealed_store import SealedScoreStore
from epistemic_loop.holdout.violations import HoldoutViolationError
from epistemic_loop.reporting.benchmark_report import write_benchmark_report
from epistemic_loop.reporting.run_report import write_run_report
from epistemic_loop.scoring.selector import score_experiment
from epistemic_loop.storage.repositories import ResearchRepository

app = typer.Typer(help="Epistemic Research Loop control CLI", no_args_is_help=True)
run_app = typer.Typer(help="Manage research runs", no_args_is_help=True)
hypotheses_app = typer.Typer(help="Inspect hypotheses", no_args_is_help=True)
experiments_app = typer.Typer(help="Inspect experiments", no_args_is_help=True)
holdout_app = typer.Typer(help="Audit holdout access", no_args_is_help=True)
benchmark_app = typer.Typer(help="Run paired benchmarks", no_args_is_help=True)
report_app = typer.Typer(help="Build reports", no_args_is_help=True)
kaggle_app = typer.Typer(help="Evaluator-only Kaggle submission automation", no_args_is_help=True)
beliefs_app = typer.Typer(help="Falsify hypotheses and update beliefs", no_args_is_help=True)
app.add_typer(run_app, name="run")
app.add_typer(hypotheses_app, name="hypotheses")
app.add_typer(experiments_app, name="experiments")
app.add_typer(holdout_app, name="holdout")
app.add_typer(benchmark_app, name="benchmark")
app.add_typer(report_app, name="report")
app.add_typer(kaggle_app, name="kaggle")
app.add_typer(beliefs_app, name="beliefs")


def _home() -> Path:
    return Path(os.environ.get("ERL_HOME", ".")).resolve()


def _repository() -> ResearchRepository:
    home = _home()
    return ResearchRepository(home / ".runs", home / ".state" / "epistemic-loop.db")


def _run_config_path(run_id: str) -> Path:
    return _home() / ".runs" / run_id / "config.yaml"


def _controller() -> ResearchController:
    return ResearchController(_repository())


def _run_config(run_id: str) -> AppConfig:
    path = _run_config_path(run_id)
    if not path.is_file():
        raise typer.BadParameter(f"unknown run: {run_id}")
    return load_config(path)


def _state(run_id: str) -> RunState:
    try:
        return _controller().state(run_id)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error


def _executor(config: AppConfig) -> ExecutorAdapter:
    result_root = _home() / config.executor.result_root
    if config.executor.adapter == "local":
        return LocalExecutor(_home() / config.executor.workspace, result_root)
    if not config.executor.linear_team_id or not config.executor.linear_project_id:
        raise typer.BadParameter("executor.linear_team_id and executor.linear_project_id must be configured")
    return AiDevControlPlaneAdapter(
        team_id=config.executor.linear_team_id,
        project_id=config.executor.linear_project_id,
        result_root=result_root,
        worker=config.executor.worker,
        handoff=config.executor.handoff,
        target_repo=config.executor.target_repo,
        state_id=config.executor.linear_state_id,
    )


def _bridge() -> ProposalBridge:
    return ProposalBridge(_home() / ".proposals", _home() / "prompts")


def _llm(config: AppConfig) -> StructuredLlm:
    if config.llm.adapter != "claude":
        raise typer.BadParameter(
            f"llm.adapter={config.llm.adapter} has no automatic driver; "
            "use 'hypotheses request/record' and 'experiments request/propose' instead"
        )
    from epistemic_loop.adapters.llm.claude import ClaudeStructuredLlm, Effort

    return ClaudeStructuredLlm(
        model=config.llm.model,
        max_tokens=config.llm.max_tokens,
        effort=cast(Effort, config.llm.effort),
    )


def _echo(payload: object) -> None:
    typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_home(),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "uncommitted"


@app.command("init")
def initialize(
    competition: str = typer.Option(..., "--competition"),
    config: Path = typer.Option(..., "--config", exists=True, dir_okay=False),
    run_id: str | None = typer.Option(None, "--run-id"),
) -> None:
    """Create an immutable run identity and its first canonical events."""
    loaded = load_config(config)
    if loaded.competition.slug != competition:
        loaded.competition.slug = competition
    controller = ResearchController(_repository())
    run = controller.create_run(
        loaded,
        base_commit_sha=_git_sha(),
        dataset_fingerprint=fingerprint_path(loaded.competition.data_path),
        run_id=run_id,
    )
    destination = _run_config_path(run.id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(yaml.safe_dump(loaded.model_dump(mode="json"), sort_keys=False), encoding="utf-8")
    typer.echo(json.dumps({"run_id": run.id, "status": run.status.value}, sort_keys=True))


@run_app.command("start")
def run_start(run_id: str = typer.Option(..., "--run-id")) -> None:
    config_path = _run_config_path(run_id)
    loaded = load_config(config_path)
    package: dict[str, Any] = {
        "metric": {"name": loaded.competition.primary_metric, "direction": loaded.competition.metric_direction},
        "target": {"semantics": "unresolved"},
        "columns": [],
        "compute_constraints": [f"max_cpu_hours={loaded.budgets.max_cpu_hours}"],
    }
    controller = ResearchController(_repository())
    controller.start(run_id, CompetitionObserver().observe(package))
    typer.echo(json.dumps({"run_id": run_id, "state": "hypothesizing", "status": "running"}))


@run_app.command("status")
def run_status(run_id: str = typer.Option(..., "--run-id")) -> None:
    events = _repository().event_store(run_id).read_all()
    if not events:
        raise typer.BadParameter(f"unknown run: {run_id}")
    state = _state(run_id)
    statuses: dict[str, int] = {}
    for value in state.experiment_statuses.values():
        statuses[value.value] = statuses.get(value.value, 0) + 1
    _echo(
        {
            "run_id": run_id,
            "competition": state.run.competition_id,
            "state": state.loop_state.value,
            "status": state.run.status.value,
            "phase": state.phase.value,
            "hypotheses": {
                "total": len(state.hypotheses),
                "supported": sum(item.status == HypothesisStatus.SUPPORTED for item in state.hypotheses.values()),
                "falsified": sum(item.status == HypothesisStatus.FALSIFIED for item in state.hypotheses.values()),
            },
            "experiments": statuses,
            "observations": len(state.observations),
            "violations": state.violations,
            "remaining_budget": BudgetManager(state.run.budgets, state.usage).remaining(),
            "event_count": len(events),
            "last_sequence": events[-1].sequence,
        }
    )


@run_app.command("replay")
def run_replay(run_id: str = typer.Option(..., "--run-id")) -> None:
    events = _repository().replay(run_id)
    typer.echo(json.dumps({"run_id": run_id, "replayed_events": len(events)}))


def _entities(run_id: str, event_type: EventType) -> list[dict[str, Any]]:
    return [event.payload for event in _repository().event_store(run_id).read_all() if event.event_type == event_type]


@hypotheses_app.command("list")
def hypotheses_list(run_id: str = typer.Option(..., "--run-id")) -> None:
    typer.echo(json.dumps(_entities(run_id, EventType.HYPOTHESIS_PROPOSED), indent=2, sort_keys=True))


@hypotheses_app.command("show")
def hypotheses_show(hypothesis_id: str) -> None:
    for event_file in sorted((_home() / ".runs").glob("*/events.jsonl")):
        events = _repository().event_store(event_file.parent.name).read_all()
        for event in events:
            if (
                event.event_type in {EventType.HYPOTHESIS_PROPOSED, EventType.HYPOTHESIS_REVISED}
                and event.payload.get("id") == hypothesis_id
            ):
                typer.echo(json.dumps(event.payload, indent=2, sort_keys=True))
                return
    raise typer.BadParameter(f"unknown hypothesis: {hypothesis_id}")


@hypotheses_app.command("graph")
def hypotheses_graph(run_id: str = typer.Option(..., "--run-id")) -> None:
    hypotheses = [Hypothesis.model_validate(item) for item in _entities(run_id, EventType.HYPOTHESIS_PROPOSED)]
    lines = ["flowchart TD"]
    for hypothesis in hypotheses:
        claim = hypothesis.claim.replace('"', "'")
        lines.append(f'  {hypothesis.id}["{claim}"]')
        for parent in hypothesis.parent_hypothesis_ids:
            lines.append(f"  {parent} -->|refines| {hypothesis.id}")
        for alternative in hypothesis.alternative_hypothesis_ids:
            lines.append(f"  {hypothesis.id} -. alternative .- {alternative}")
    typer.echo("\n".join(lines))


@experiments_app.command("candidates")
def experiments_candidates(run_id: str = typer.Option(..., "--run-id")) -> None:
    candidates = _entities(run_id, EventType.EXPERIMENT_PROPOSED)
    typer.echo(json.dumps([item for item in candidates if item.get("status") == "proposed"], indent=2, sort_keys=True))


@experiments_app.command("history")
def experiments_history(run_id: str = typer.Option(..., "--run-id")) -> None:
    events = _repository().event_store(run_id).read_all()
    history_types = {
        EventType.EXPERIMENT_PROPOSED,
        EventType.EXPERIMENT_SELECTED,
        EventType.EXPERIMENT_STARTED,
        EventType.EXPERIMENT_COMPLETED,
        EventType.EXPERIMENT_FAILED,
    }
    typer.echo(
        json.dumps(
            [
                {"sequence": event.sequence, "type": event.event_type.value, "payload": event.payload}
                for event in events
                if event.event_type in history_types
            ],
            indent=2,
            sort_keys=True,
        )
    )


@experiments_app.command("utility")
def experiments_utility(experiment_id: str) -> None:
    for event_file in sorted((_home() / ".runs").glob("*/events.jsonl")):
        run_id = event_file.parent.name
        for payload in _entities(run_id, EventType.EXPERIMENT_PROPOSED):
            if payload.get("id") != experiment_id:
                continue
            proposal = ExperimentProposal.model_validate(payload)
            config = load_config(_run_config_path(run_id))
            weights = config.selection.for_phase(_current_phase(run_id))
            breakdown = score_experiment(proposal, weights, config.selection.cost_lambda)
            typer.echo(json.dumps(breakdown.__dict__, indent=2, sort_keys=True))
            return
    raise typer.BadParameter(f"unknown experiment: {experiment_id}")


def _current_phase(run_id: str) -> Phase:
    events = _repository().event_store(run_id).read_all()
    value = next(
        (event.payload["phase"] for event in reversed(events) if event.event_type == EventType.PHASE_CHANGED),
        "discovery",
    )
    return Phase(value)


@holdout_app.command("status")
def holdout_status(run_id: str = typer.Option(..., "--run-id")) -> None:
    events = _repository().event_store(run_id).read_all()
    run = next(event.payload for event in events if event.event_type == EventType.RUN_CREATED)
    violations = sum(event.event_type == EventType.VIOLATION_DETECTED for event in events)
    typer.echo(json.dumps({"run_id": run_id, "policy": run["holdout_policy"], "violations": violations}, indent=2))


@holdout_app.command("violations")
def holdout_violations(run_id: str = typer.Option(..., "--run-id")) -> None:
    typer.echo(json.dumps(_entities(run_id, EventType.VIOLATION_DETECTED), indent=2, sort_keys=True))


@hypotheses_app.command("request")
def hypotheses_request(run_id: str = typer.Option(..., "--run-id")) -> None:
    """Write the hypothesis-generation prompt, context, and JSON Schema for the proposing agent."""
    events = _repository().event_store(run_id).read_all()
    payload = next(
        (event.payload for event in reversed(events) if event.event_type == EventType.WORLD_MODEL_RECORDED),
        None,
    )
    if payload is None:
        raise typer.BadParameter(f"run {run_id} has no world model; run 'erlctl run start' first")
    world_model = CompetitionWorldModel.model_validate(payload)
    typer.echo(str(_bridge().request_hypotheses(run_id, world_model, _state(run_id))))


@hypotheses_app.command("record")
def hypotheses_record(
    run_id: str = typer.Option(..., "--run-id"),
    source: Path = typer.Option(..., "--from", exists=True, dir_okay=False),
) -> None:
    """Validate proposed hypotheses against the domain schema and append them to the event log."""
    config = _run_config(run_id)
    try:
        hypotheses = ProposalBridge.load_hypotheses(source)
        recorded = _controller().record_hypotheses(run_id, hypotheses, max_active=config.loop.max_active_hypotheses)
    except (ValueError, LoopStateError) as error:
        raise typer.BadParameter(str(error)) from error
    _echo({"run_id": run_id, "recorded": recorded})


@experiments_app.command("request")
def experiments_request(run_id: str = typer.Option(..., "--run-id")) -> None:
    """Write the experiment-design prompt, context, and JSON Schema for the proposing agent."""
    typer.echo(str(_bridge().request_experiments(run_id, _state(run_id))))


@experiments_app.command("propose")
def experiments_propose(
    run_id: str = typer.Option(..., "--run-id"),
    source: Path = typer.Option(..., "--from", exists=True, dir_okay=False),
) -> None:
    """Record preregistered experiment candidates; gates and utility run later at selection."""
    try:
        proposals = ProposalBridge.load_experiments(source)
        recorded = _controller().record_proposals(run_id, proposals)
    except (ValueError, LoopStateError) as error:
        raise typer.BadParameter(str(error)) from error
    _echo({"run_id": run_id, "proposed": recorded})


@experiments_app.command("select")
def experiments_select(
    run_id: str = typer.Option(..., "--run-id"),
    size: int = typer.Option(1, "--size", min=1),
) -> None:
    """Apply hard gates, phase-weighted utility, and similarity-penalized portfolio selection."""
    config = _run_config(run_id)
    state = _state(run_id)
    try:
        decision = _controller().select_experiments(
            run_id,
            weights=config.selection.for_phase(state.phase),
            cost_lambda=config.selection.cost_lambda,
            size=size,
            minimum_utility=config.selection.minimum_utility,
            source_policy_strict=config.contamination.require_source_provenance,
        )
    except (ValueError, LoopStateError) as error:
        raise typer.BadParameter(str(error)) from error
    _echo(decision.model_dump(mode="json"))


@experiments_app.command("dispatch")
def experiments_dispatch(
    run_id: str = typer.Option(..., "--run-id"),
    experiment_id: str = typer.Option(..., "--experiment-id"),
    attempt: int = typer.Option(1, "--attempt", min=1),
) -> None:
    """Hand the execution contract to the configured executor and record the attempt."""
    config = _run_config(run_id)
    try:
        request, result = _controller().dispatch(
            run_id,
            experiment_id,
            _executor(config),
            container_image=config.executor.container_image,
            dataset_mounts=config.executor.dataset_mounts,
            network_policy=config.contamination.worker_network,
            attempt=attempt,
        )
    except (ValueError, LoopStateError, PermissionError, RuntimeError) as error:
        raise typer.BadParameter(str(error)) from error
    _echo(
        {
            "run_id": run_id,
            "experiment_id": experiment_id,
            "adapter": config.executor.adapter,
            "idempotency_key": request.idempotency_key,
            "status": result.status,
            "external_ref": result.external_ref,
        }
    )


@experiments_app.command("import-result")
def experiments_import_result(
    run_id: str = typer.Option(..., "--run-id"),
    experiment_id: str = typer.Option(..., "--experiment-id"),
) -> None:
    """Import the worker's ExperimentResult and derive an Observation from local metrics."""
    config = _run_config(run_id)
    source = result_path(_home() / config.executor.result_root, run_id, experiment_id)
    if not source.is_file():
        raise typer.BadParameter(f"no result has been written yet: {source}")
    result = ExperimentResult.model_validate_json(source.read_text(encoding="utf-8"))
    try:
        observation = _controller().import_result(run_id, result, artifact_root=source.parent)
    except (ValueError, LoopStateError) as error:
        raise typer.BadParameter(str(error)) from error
    if observation is None:
        _echo({"experiment_id": experiment_id, "status": result.status, "imported": False})
        return
    _echo(
        {
            "experiment_id": experiment_id,
            "status": result.status,
            "observation_id": observation.id,
            "metrics": observation.metrics,
        }
    )


@beliefs_app.command("update")
def beliefs_update(
    run_id: str = typer.Option(..., "--run-id"),
    source: Path = typer.Option(..., "--from", exists=True, dir_okay=False),
) -> None:
    """Record a falsification verdict and the log-odds belief update it implies."""
    payload = json.loads(source.read_text(encoding="utf-8"))
    state = _state(run_id)
    hypothesis = state.hypotheses.get(str(payload.get("hypothesis_id")))
    if hypothesis is None:
        raise typer.BadParameter(f"unknown hypothesis: {payload.get('hypothesis_id')}")
    observations = [state.observations[key] for key in payload.get("observation_ids", []) if key in state.observations]
    if not observations:
        raise typer.BadParameter("observation_ids must reference recorded observations")
    try:
        record = Falsifier().record(
            hypothesis,
            observations,
            supporting_predictions=list(payload.get("supporting_predictions", [])),
            contradicting_predictions=list(payload.get("contradicting_predictions", [])),
            alternative_explanation=str(payload.get("alternative_explanation", "")),
            confounders_checked=list(payload.get("confounders_checked", [])),
            recommended_next_test=payload.get("recommended_next_test"),
        )
        controller = _controller()
        controller.record_falsification(run_id, record)
        update = belief_update(
            hypothesis.id,
            hypothesis.current_confidence,
            interpret_evidence(record),
            str(payload.get("evidence_summary") or f"falsification disposition: {record.disposition.value}"),
            [item.id for item in observations],
            VerifierResult(payload.get("verifier_result", VerifierResult.PASS.value)),
        )
        status = payload.get("status")
        revised = controller.record_belief_update(
            run_id,
            update,
            status=HypothesisStatus(status) if status else DISPOSITION_STATUS[record.disposition],
        )
    except (ValueError, LoopStateError) as error:
        raise typer.BadParameter(str(error)) from error
    _echo(
        {
            "hypothesis_id": hypothesis.id,
            "disposition": record.disposition.value,
            "prior_confidence": update.prior_confidence,
            "posterior_confidence": update.posterior_confidence,
            "status": revised.status.value,
        }
    )


@run_app.command("loop")
def run_loop(
    run_id: str = typer.Option(..., "--run-id"),
    rounds: int = typer.Option(1, "--rounds", min=1),
    size: int = typer.Option(1, "--size", min=1),
    poll_seconds: float = typer.Option(10.0, "--poll-seconds", min=0.0),
    timeout_seconds: float = typer.Option(3600.0, "--timeout-seconds", min=1.0),
) -> None:
    """Run the full cycle without hand-off: propose, gate, select, dispatch, import, falsify, update."""
    config = _run_config(run_id)
    loop = AutonomousLoop(
        _controller(),
        AutomaticProposer(_llm(config), _bridge()),
        _executor(config),
        config=config,
        home=_home(),
    )
    settings = LoopSettings(
        rounds=rounds,
        portfolio_size=size,
        poll_seconds=poll_seconds,
        timeout_seconds=timeout_seconds,
    )
    try:
        outcomes = loop.run(run_id, settings)
    except (ValueError, LoopStateError, PermissionError, RuntimeError) as error:
        raise typer.BadParameter(str(error)) from error
    _echo({"run_id": run_id, "rounds": [outcome.__dict__ for outcome in outcomes]})


@run_app.command("advance")
def run_advance(
    run_id: str = typer.Option(..., "--run-id"),
    validation_locked: bool = typer.Option(False, "--validation-locked"),
    critical_leakage_resolved: bool = typer.Option(False, "--leakage-resolved"),
    stable_lineages: int = typer.Option(0, "--stable-lineages", min=0),
    ablations_complete: bool = typer.Option(False, "--ablations-complete"),
    search_space_defined: bool = typer.Option(False, "--search-space-defined"),
    anomaly_detected: bool = typer.Option(False, "--anomaly-detected"),
) -> None:
    """Run the deterministic phase policy and reopen the loop for the next round."""
    evidence = PhaseEvidence(
        validation_locked=validation_locked,
        critical_leakage_resolved=critical_leakage_resolved,
        stable_lineages=stable_lineages,
        ablations_complete=ablations_complete,
        search_space_defined=search_space_defined,
        anomaly_detected=anomaly_detected,
    )
    try:
        phase = _controller().advance_phase(run_id, evidence)
    except (ValueError, LoopStateError) as error:
        raise typer.BadParameter(str(error)) from error
    _echo({"run_id": run_id, "phase": phase.value, "state": _state(run_id).loop_state.value})


def _submission_candidates(path: Path) -> list[SubmissionCandidate]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    values = raw.get("candidates", raw) if isinstance(raw, dict) else raw
    if not isinstance(values, list):
        raise typer.BadParameter("candidate file must contain a list or a candidates list")
    return [SubmissionCandidate(**value) for value in values]


@kaggle_app.command("plan")
def kaggle_plan(
    competition: str = typer.Option(..., "--competition"),
    candidates: Path = typer.Option(..., "--candidates", exists=True, dir_okay=False),
    daily_cap: int = typer.Option(1, "--daily-cap", min=1),
    ledger_path: Path = typer.Option(Path(".state/kaggle-submissions.jsonl"), "--ledger"),
) -> None:
    ledger = SubmissionLedger(ledger_path)
    plan = plan_submission(
        competition,
        _submission_candidates(candidates),
        submitted_today=ledger.submitted_today(competition),
        daily_cap=daily_cap,
        submitted_fingerprints=ledger.fingerprints(competition),
    )
    typer.echo(json.dumps(plan, default=lambda value: value.__dict__, indent=2, sort_keys=True))


@kaggle_app.command("submit")
def kaggle_submit(
    competition: str = typer.Option(..., "--competition"),
    submission: Path = typer.Option(..., "--file", exists=True, dir_okay=False),
    message: str = typer.Option(..., "--message"),
    run_id: str = typer.Option(..., "--run-id"),
    daily_cap: int = typer.Option(1, "--daily-cap", min=1),
    ledger_path: Path = typer.Option(Path(".state/kaggle-submissions.jsonl"), "--ledger"),
    wait: bool = typer.Option(True, "--wait/--no-wait"),
    seal_scores: bool = typer.Option(True, "--seal-scores/--show-scores"),
) -> None:
    ledger = SubmissionLedger(ledger_path)
    digest = fingerprint(submission)
    if ledger.submitted_today(competition) >= daily_cap:
        raise typer.BadParameter("daily submission cap reached")
    if digest in ledger.fingerprints(competition):
        raise typer.BadParameter("this exact artifact was already submitted")
    if not seal_scores:
        raise typer.BadParameter("plaintext score output is forbidden; use evaluator unseal after paired runs")
    adapter = KaggleCliSubmissionAdapter()
    receipt = adapter.submit(competition, submission, message)
    row = adapter.wait_for_terminal_status(competition, reference=receipt.reference) if wait else None
    record: dict[str, Any] = {
        "created_at": datetime.now(UTC).isoformat(),
        "mode": "execute",
        "competition": competition,
        "run_id": run_id,
        "sha256": digest,
        "submission_file": str(submission.resolve()),
        "message": message,
        "reference": receipt.reference,
        "status": row.get("status") if row else "submitted",
    }
    if row is not None:
        token = os.environ.get("BENCHMARK_UNSEAL_TOKEN")
        if not token:
            raise typer.BadParameter("BENCHMARK_UNSEAL_TOKEN is required to seal returned scores")
        score_id = f"{run_id}-{receipt.reference or digest[:12]}"
        SealedScoreStore(_home() / _run_config(run_id).leaderboard.sealed_store).seal(
            score_id,
            {"public_score": row.get("publicScore"), "private_score": row.get("privateScore")},
            token,
        )
        record["score_id"] = score_id
    ledger.append(record)
    typer.echo(json.dumps({"reference": receipt.reference, "status": record["status"], "scores": "sealed"}))


@kaggle_app.command("manual-packet")
def kaggle_manual_packet(
    competition: str = typer.Option(..., "--competition"),
    submission: Path = typer.Option(..., "--file", exists=True, dir_okay=False),
    message: str = typer.Option(..., "--message"),
    run_id: str = typer.Option(..., "--run-id"),
    output: Path = typer.Option(..., "--output"),
) -> None:
    write_manual_packet(
        manual_submission_packet(submission, competition_slug=competition, message=message, run_id=run_id),
        output,
    )
    typer.echo(str(output))


@kaggle_app.command("feedback")
def kaggle_feedback(
    run_id: str = typer.Option(..., "--run-id"),
    score_id: str = typer.Option(..., "--score-id"),
    threshold: float | None = typer.Option(None, "--threshold"),
    actor: str = typer.Option("evaluator", "--actor"),
    unseal_token_env: str = typer.Option("BENCHMARK_UNSEAL_TOKEN", "--unseal-token-env"),
) -> None:
    """Return budgeted public-leaderboard feedback. The private score is never unsealed here."""
    config = _run_config(run_id)
    token = os.environ.get(unseal_token_env)
    if not token:
        raise typer.BadParameter(f"{unseal_token_env} is not set")
    store = SealedScoreStore(_home() / config.leaderboard.sealed_store)
    try:
        sealed = store.unseal(score_id, token)
    except (FileNotFoundError, ValueError) as error:
        raise typer.BadParameter(f"cannot unseal {score_id}: {error}") from error
    gate = LeaderboardGate(
        run_id,
        config.leaderboard.public_feedback,
        QueryLedger(_home() / config.leaderboard.query_ledger),
        max_queries=config.leaderboard.max_public_queries,
    )
    controller = _controller()
    try:
        feedback = gate.evaluate(sealed, actor=actor, threshold=threshold)
    except HoldoutViolationError as error:
        controller.record_violation(run_id, error.violation)
        raise typer.BadParameter(error.violation.description) from error
    payload = {
        "score_id": score_id,
        "mode": config.leaderboard.public_feedback.value,
        "threshold": threshold,
        "passed": feedback.passed,
        "public_score": feedback.public_score,
        "response_kind": feedback.response_kind,
        "queries_used": feedback.queries_used,
        "queries_remaining": feedback.queries_remaining,
    }
    controller.record_leaderboard_feedback(run_id, payload)
    _echo(payload)


@benchmark_app.command("plan")
def benchmark_plan(
    profile: Path = typer.Option(..., "--profile", exists=True, dir_okay=False),
    replicates: int = typer.Option(5, "--replicates", min=3),
    output: Path = typer.Option(Path("benchmark-plan.yaml"), "--output"),
) -> None:
    raw = yaml.safe_load(profile.read_text(encoding="utf-8")) or {}
    scenarios = raw.get("synthetic_scenarios") or [
        "temporal_shift",
        "spurious_leakage",
        "candidate_generation_bottleneck",
        "iid_easy",
    ]
    benchmark_id = raw.get("benchmark_id") or f"{profile.stem}-ab-001"
    plan = BenchmarkPlan(
        benchmark_id=benchmark_id,
        scenarios=scenarios,
        replicates=replicates,
        seeds=[101 + index * 17 for index in range(replicates)],
        budgets=raw.get("budgets", {"max_experiments": 40, "max_cpu_hours": 120}),
    )
    save_plan(plan, output)
    typer.echo(str(output))


@benchmark_app.command("run")
def benchmark_run(
    plan_path: Path = typer.Option(..., "--plan", exists=True, dir_okay=False),
    output_root: Path = typer.Option(Path(".benchmarks"), "--output-root"),
) -> None:
    token = os.environ.get("BENCHMARK_UNSEAL_TOKEN")
    if not token:
        raise typer.BadParameter("BENCHMARK_UNSEAL_TOKEN must be set by the evaluator")
    try:
        SealedScoreStore.validate_token(token)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error
    plan = load_plan(plan_path)
    paths = run_synthetic_plan(plan, output_root / plan.benchmark_id, unseal_token=token)
    typer.echo(json.dumps({"benchmark_id": plan.benchmark_id, "runs": len(paths), "scores": "sealed"}))


@benchmark_app.command("finalize")
def benchmark_finalize(
    plan_path: Path = typer.Option(..., "--plan", exists=True, dir_okay=False),
    unseal_token_env: str = typer.Option("BENCHMARK_UNSEAL_TOKEN", "--unseal-token-env"),
    output_root: Path = typer.Option(Path(".benchmarks"), "--output-root"),
) -> None:
    token = os.environ.get(unseal_token_env)
    if not token:
        raise typer.BadParameter(f"{unseal_token_env} is not set")
    try:
        SealedScoreStore.validate_token(token)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error
    plan = load_plan(plan_path)
    root = output_root / plan.benchmark_id
    result = finalize_benchmark(plan, root, unseal_token=token)
    result_path = root / "benchmark-result.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    write_benchmark_report(result, root / "benchmark-report.md")
    typer.echo(str(result_path))


@report_app.command("run")
def report_run(run_id: str = typer.Option(..., "--run-id")) -> None:
    events = _repository().event_store(run_id).read_all()
    destination = _home() / ".runs" / run_id / "report.md"
    write_run_report(run_id, events, destination)
    typer.echo(str(destination))


@report_app.command("benchmark")
def report_benchmark(benchmark_id: str = typer.Option(..., "--benchmark-id")) -> None:
    root = _home() / ".benchmarks" / benchmark_id
    result = json.loads((root / "benchmark-result.json").read_text(encoding="utf-8"))
    destination = write_benchmark_report(result, root / "benchmark-report.md")
    typer.echo(str(destination))


if __name__ == "__main__":
    app()
