from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer
import yaml

from epistemic_loop.adapters.kaggle import (
    KaggleCliSubmissionAdapter,
    SubmissionCandidate,
    SubmissionLedger,
    fingerprint,
    plan_submission,
)
from epistemic_loop.adapters.kaggle.manual import manual_submission_packet, write_manual_packet
from epistemic_loop.agents.observer import CompetitionObserver
from epistemic_loop.benchmark.evaluator import finalize_benchmark
from epistemic_loop.benchmark.paired_runner import run_synthetic_plan
from epistemic_loop.benchmark.protocol import BenchmarkPlan, load_plan, save_plan
from epistemic_loop.config import load_config
from epistemic_loop.controller.research_graph import (
    ResearchController,
    fingerprint_path,
)
from epistemic_loop.domain.enums import Phase
from epistemic_loop.domain.events import EventType
from epistemic_loop.domain.models import ExperimentProposal, Hypothesis
from epistemic_loop.holdout.sealed_store import SealedScoreStore
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
app.add_typer(run_app, name="run")
app.add_typer(hypotheses_app, name="hypotheses")
app.add_typer(experiments_app, name="experiments")
app.add_typer(holdout_app, name="holdout")
app.add_typer(benchmark_app, name="benchmark")
app.add_typer(report_app, name="report")
app.add_typer(kaggle_app, name="kaggle")


def _home() -> Path:
    return Path(os.environ.get("ERL_HOME", ".")).resolve()


def _repository() -> ResearchRepository:
    home = _home()
    return ResearchRepository(home / ".runs", home / ".state" / "epistemic-loop.db")


def _run_config_path(run_id: str) -> Path:
    return _home() / ".runs" / run_id / "config.yaml"


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
    run = next(event.payload for event in events if event.event_type == EventType.RUN_CREATED)
    latest_state = next(
        (event.payload for event in reversed(events) if event.event_type == EventType.STATE_CHANGED),
        {},
    )
    phase = next(
        (event.payload["phase"] for event in reversed(events) if event.event_type == EventType.PHASE_CHANGED),
        run["phase"],
    )
    typer.echo(
        json.dumps(
            {
                "run_id": run_id,
                "competition": run["competition_id"],
                "state": latest_state.get("state", "created"),
                "status": latest_state.get("run_status", run["status"]),
                "phase": phase,
                "event_count": len(events),
                "last_sequence": events[-1].sequence,
            },
            indent=2,
            sort_keys=True,
        )
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
        SealedScoreStore(_home() / ".sealed-scores").seal(
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
