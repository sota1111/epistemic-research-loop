from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from epistemic_loop.adapters.executor.local import LocalExecutor
from epistemic_loop.agents.auto import AutomaticProposer
from epistemic_loop.agents.proposal_bridge import (
    ExperimentBatch,
    FalsificationAssessment,
    HypothesisBatch,
    ProposalBridge,
)
from epistemic_loop.config import AppConfig, CompetitionConfig, ExecutorConfig, RunConfig
from epistemic_loop.controller.autoloop import AutonomousLoop, LoopSettings
from epistemic_loop.controller.research_graph import ResearchController
from epistemic_loop.domain.enums import HypothesisStatus, VerifierResult
from epistemic_loop.domain.models import (
    CompetitionWorldModel,
    ExperimentProposal,
    Hypothesis,
)
from epistemic_loop.storage.repositories import ResearchRepository

ROOT = Path(__file__).resolve().parents[2]

WORKER = """
import json, os, pathlib
out = pathlib.Path(os.environ["ERL_OUTPUT_DIR"])
out.mkdir(parents=True, exist_ok=True)
(out / "metrics.json").write_text(json.dumps({"auc_gap": 0.061}))
(out / "fold_metrics.json").write_text(json.dumps({"folds": [0.05, 0.07]}))
"""


class ScriptedLlm:
    """Deterministic stand-in for the proposal model; records what it was asked."""

    def __init__(self, hypotheses: list[Hypothesis], experiments: list[ExperimentProposal]):
        self.hypotheses = hypotheses
        self.experiments = experiments
        self.calls: list[str] = []

    def generate(self, prompt: str, schema: type[BaseModel], context: dict[str, Any]) -> Any:
        self.calls.append(schema.__name__)
        if schema is HypothesisBatch:
            return HypothesisBatch(hypotheses=self.hypotheses)
        if schema is ExperimentBatch:
            return ExperimentBatch(experiments=self.experiments)
        if schema is FalsificationAssessment:
            assert context["observations"], "the falsifier must see the observation it judges"
            return FalsificationAssessment(
                hypothesis_id=context["hypothesis"]["id"],
                supporting_predictions=["temporal CV score is lower than random CV"],
                contradicting_predictions=[],
                alternative_explanation="fold-size differences rather than temporal leakage",
                confounders_checked=["fold size", "feature set", "seed"],
                verifier_result=VerifierResult.PASS,
                evidence_summary="observed gap 0.061 exceeds the preregistered 0.02 threshold",
            )
        raise AssertionError(f"unexpected schema: {schema}")


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "worker.py").write_text(WORKER, encoding="utf-8")
    return tmp_path


@pytest.fixture
def config(workspace: Path) -> AppConfig:
    return AppConfig(
        run=RunConfig(id="auto-001"),
        competition=CompetitionConfig(slug="example", metric_direction="maximize"),
        executor=ExecutorConfig(
            adapter="local",
            result_root=str(workspace / "results"),
            workspace=str(workspace),
        ),
    )


def test_one_autonomous_round_completes_the_whole_cycle(
    workspace: Path,
    config: AppConfig,
    hypothesis: Hypothesis,
    proposal: ExperimentProposal,
    clone_proposal,
) -> None:
    controller = ResearchController(ResearchRepository(workspace / ".runs", workspace / "projection.db"))
    controller.create_run(config, base_commit_sha="abc123", dataset_fingerprint="f" * 64, run_id="auto-001")
    controller.start("auto-001", CompetitionWorldModel(unresolved_questions=["which split?"]))

    runnable = clone_proposal(
        proposal,
        run_id="auto-001",
        implementation_request={"command": f"python3 {workspace / 'worker.py'}"},
    )
    llm = ScriptedLlm([hypothesis.model_copy(update={"run_id": "auto-001"})], [runnable])
    loop = AutonomousLoop(
        controller,
        AutomaticProposer(llm, ProposalBridge(workspace / ".proposals", ROOT / "prompts")),
        LocalExecutor(workspace, workspace / "results"),
        config=config,
        home=workspace,
        sleep=lambda _: None,
    )

    outcomes = loop.run("auto-001", LoopSettings(rounds=1, poll_seconds=0, timeout_seconds=5))

    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome.hypotheses == ["H-001"]
    assert outcome.experiments == ["EXP-001"]
    assert outcome.selected == ["EXP-001"]
    assert len(outcome.observations) == 1
    assert outcome.beliefs == ["H-001"]
    assert outcome.pending == []
    assert llm.calls == ["HypothesisBatch", "ExperimentBatch", "FalsificationAssessment"]

    state = controller.state("auto-001")
    assert state.hypotheses["H-001"].status == HypothesisStatus.SUPPORTED
    assert state.hypotheses["H-001"].current_confidence > 0.5
    observation = next(iter(state.observations.values()))
    assert observation.metrics == {"auc_gap": 0.061}
    assert observation.fold_metrics == {"folds": [0.05, 0.07]}
    assert state.usage.experiments == 1

    events = controller.repository.event_store("auto-001").read_all()
    recorded = {event.event_type.value for event in events}
    assert {
        "HypothesisProposed",
        "ExperimentProposed",
        "ExperimentSelected",
        "ExperimentStarted",
        "ExperimentCompleted",
        "ObservationRecorded",
        "FalsificationRecorded",
        "BeliefUpdated",
    } <= recorded


def test_the_loop_stops_when_a_result_never_arrives(
    workspace: Path,
    config: AppConfig,
    hypothesis: Hypothesis,
    proposal: ExperimentProposal,
    clone_proposal,
) -> None:
    controller = ResearchController(ResearchRepository(workspace / ".runs", workspace / "projection.db"))
    controller.create_run(config, base_commit_sha="abc123", dataset_fingerprint="f" * 64, run_id="auto-001")
    controller.start("auto-001", CompetitionWorldModel())

    silent = clone_proposal(
        proposal,
        run_id="auto-001",
        implementation_request={"command": "python3 -c pass"},
    )

    class NeverWrites:
        def submit(self, request: Any) -> Any:
            from epistemic_loop.domain.models import ExperimentResult

            return ExperimentResult(
                experiment_id=request.experiment_id,
                run_id=request.run_id,
                attempt=1,
                status="queued",
                commit_sha=request.base_commit_sha,
                environment_hash="pending",
                dataset_fingerprint="pending",
            )

        def result(self, request: Any) -> None:
            return None

    ticks = iter([0.0, 1.0, 2.0, 3.0, 99.0, 100.0])
    loop = AutonomousLoop(
        controller,
        AutomaticProposer(
            ScriptedLlm([hypothesis.model_copy(update={"run_id": "auto-001"})], [silent]),
            ProposalBridge(workspace / ".proposals", ROOT / "prompts"),
        ),
        NeverWrites(),  # type: ignore[arg-type]
        config=config,
        home=workspace,
        sleep=lambda _: None,
        now=lambda: next(ticks),
    )

    outcomes = loop.run("auto-001", LoopSettings(rounds=3, poll_seconds=0, timeout_seconds=2))
    assert len(outcomes) == 1, "a pending experiment must stop the loop rather than pile up work"
    assert outcomes[0].pending == ["EXP-001"]
    assert outcomes[0].observations == []


def test_the_proposer_normalizes_run_id_but_not_the_science(
    workspace: Path, hypothesis: Hypothesis, proposal: ExperimentProposal, clone_proposal
) -> None:
    stray = hypothesis.model_copy(update={"run_id": "some-other-run"})
    strayed_experiment = clone_proposal(proposal, run_id="some-other-run")
    proposer = AutomaticProposer(
        ScriptedLlm([stray], [strayed_experiment]),
        ProposalBridge(workspace / ".proposals", ROOT / "prompts"),
    )
    controller = ResearchController(ResearchRepository(workspace / ".runs", workspace / "projection.db"))
    config = AppConfig(
        run=RunConfig(id="auto-001"),
        competition=CompetitionConfig(slug="example", metric_direction="maximize"),
    )
    controller.create_run(config, base_commit_sha="abc", dataset_fingerprint="f" * 64, run_id="auto-001")
    state = controller.state("auto-001")

    produced = proposer.hypotheses("auto-001", CompetitionWorldModel(), state)
    assert produced[0].run_id == "auto-001"
    assert produced[0].claim == hypothesis.claim
    assert produced[0].prior_confidence == hypothesis.prior_confidence

    designed = proposer.experiments("auto-001", state)
    assert designed[0].run_id == "auto-001"
    assert designed[0].decision_rule == proposal.decision_rule


def test_requests_are_reproducible_as_files(workspace: Path, hypothesis: Hypothesis) -> None:
    controller = ResearchController(ResearchRepository(workspace / ".runs", workspace / "projection.db"))
    config = AppConfig(
        run=RunConfig(id="auto-001"),
        competition=CompetitionConfig(slug="example", metric_direction="maximize"),
    )
    controller.create_run(config, base_commit_sha="abc", dataset_fingerprint="f" * 64, run_id="auto-001")
    bridge = ProposalBridge(workspace / ".proposals", ROOT / "prompts")
    state = controller.state("auto-001")
    request = bridge.hypothesis_request("auto-001", CompetitionWorldModel(), state)
    written = json.loads(bridge.write(request).read_text(encoding="utf-8"))
    assert written["prompt"] == request.prompt
    assert written["json_schema"] == request.json_schema


def test_the_loop_resumes_an_interrupted_round_without_reproposing(
    workspace: Path,
    config: AppConfig,
    hypothesis: Hypothesis,
    proposal: ExperimentProposal,
    clone_proposal,
) -> None:
    """A hand-off that failed mid-round must be picked up, not restarted from hypothesizing."""
    controller = ResearchController(ResearchRepository(workspace / ".runs", workspace / "projection.db"))
    controller.create_run(config, base_commit_sha="abc123", dataset_fingerprint="f" * 64, run_id="auto-001")
    controller.start("auto-001", CompetitionWorldModel())

    runnable = clone_proposal(
        proposal,
        run_id="auto-001",
        implementation_request={"command": f"python3 {workspace / 'worker.py'}"},
    )
    controller.record_hypotheses("auto-001", [hypothesis.model_copy(update={"run_id": "auto-001"})])
    controller.record_proposals("auto-001", [runnable])
    controller.select_experiments(
        "auto-001", weights=config.selection.for_phase(controller.state("auto-001").phase), size=1
    )

    llm = ScriptedLlm([], [])
    loop = AutonomousLoop(
        controller,
        AutomaticProposer(llm, ProposalBridge(workspace / ".proposals", ROOT / "prompts")),
        LocalExecutor(workspace, workspace / "results"),
        config=config,
        home=workspace,
        sleep=lambda _: None,
    )

    outcome = loop.run("auto-001", LoopSettings(rounds=1, poll_seconds=0, timeout_seconds=5))[0]

    assert outcome.hypotheses == [], "an already-populated run must not re-propose hypotheses"
    assert outcome.experiments == []
    assert outcome.selected == [], "selection already happened; the round resumes at dispatch"
    assert len(outcome.observations) == 1
    assert outcome.beliefs == ["H-001"]
    assert llm.calls == ["FalsificationAssessment"], "only the unfinished judgement is asked for"
    assert controller.state("auto-001").hypotheses["H-001"].status == HypothesisStatus.SUPPORTED
