from __future__ import annotations

import json
from pathlib import Path

import pytest

from epistemic_loop.adapters.executor.base import ExecutorAdapter
from epistemic_loop.belief.evidence import EvidenceLevel
from epistemic_loop.belief.updater import belief_update
from epistemic_loop.config import AppConfig, CompetitionConfig, PhaseWeights, RunConfig
from epistemic_loop.controller.phase_policy import PhaseEvidence
from epistemic_loop.controller.research_graph import LoopStateError, ResearchController
from epistemic_loop.domain.enums import (
    ExperimentStatus,
    FalsificationDisposition,
    HypothesisStatus,
    LoopState,
    Phase,
    VerifierResult,
)
from epistemic_loop.domain.models import (
    CompetitionWorldModel,
    ExperimentProposal,
    ExperimentRequest,
    ExperimentResult,
    FalsificationRecord,
    Hypothesis,
    HypothesisOutcomeForecast,
    OutcomeLikelihood,
)
from epistemic_loop.storage.repositories import ResearchRepository

WEIGHTS = PhaseWeights(pragmatic=0.2, epistemic=0.45, robustness=0.2, diversity=0.15)


class StubExecutor(ExecutorAdapter):
    def __init__(self, status: str = "completed", metrics: dict[str, float] | None = None):
        self.status = status
        self.metrics = metrics or {"auc_gap": 0.05}
        self.requests: list[ExperimentRequest] = []

    def submit(self, request: ExperimentRequest) -> ExperimentResult:
        self.requests.append(request)
        return ExperimentResult(
            experiment_id=request.experiment_id,
            run_id=request.run_id,
            attempt=1,
            status=self.status,  # type: ignore[arg-type]
            commit_sha=request.base_commit_sha,
            environment_hash="env",
            dataset_fingerprint="data",
            metrics=self.metrics,
        )

    def result(self, request: ExperimentRequest) -> ExperimentResult | None:
        return None


@pytest.fixture
def controller(tmp_path: Path) -> ResearchController:
    return ResearchController(ResearchRepository(tmp_path / ".runs", tmp_path / "projection.db"))


@pytest.fixture
def config() -> AppConfig:
    return AppConfig(
        run=RunConfig(id="run-001"),
        competition=CompetitionConfig(slug="example", metric_direction="maximize"),
    )


@pytest.fixture
def started(controller: ResearchController, config: AppConfig) -> ResearchController:
    controller.create_run(config, base_commit_sha="abc123", dataset_fingerprint="f" * 64, run_id="run-001")
    controller.start("run-001", CompetitionWorldModel())
    return controller


def _dispatch(controller: ResearchController, executor: ExecutorAdapter, experiment_id: str = "EXP-001"):
    return controller.dispatch(
        "run-001", experiment_id, executor, container_image="research:1", dataset_mounts=["train"]
    )


def test_full_loop_records_every_transition(
    started: ResearchController, hypothesis: Hypothesis, proposal: ExperimentProposal
) -> None:
    started.record_hypotheses("run-001", [hypothesis])
    assert started.state("run-001").loop_state == LoopState.PLANNING

    forecast = HypothesisOutcomeForecast(
        hypothesis_id="H-001",
        outcomes=[
            OutcomeLikelihood(label="gap", probability_if_true=0.9, probability_if_false=0.1),
            OutcomeLikelihood(label="no_gap", probability_if_true=0.1, probability_if_false=0.9),
        ],
        decisions_affected=["validation scheme"],
        measurement_notes="same models and seeds",
    )
    proposal = proposal.model_copy(update={"outcome_forecasts": [forecast]})
    started.record_proposals("run-001", [proposal])
    assert started.state("run-001").loop_state == LoopState.SCORING

    decision = started.select_experiments("run-001", weights=WEIGHTS, size=1)
    assert decision.selected_experiment_ids == ["EXP-001"]
    assert decision.rejected_reasons == {}
    assert decision.phase == Phase.DISCOVERY
    assert decision.policy_version == "selection/v2"
    assert decision.utility_breakdown["EXP-001"]["epistemic_method"] == "expected_information_gain_v2"

    state = started.state("run-001")
    assert state.experiment_statuses["EXP-001"] == ExperimentStatus.SELECTED
    assert state.usage.experiments == 1
    assert state.usage.cpu_hours == pytest.approx(1.0)

    executor = StubExecutor()
    request, result = _dispatch(started, executor)
    assert request.idempotency_key == "run-001:EXP-001:attempt-1"
    assert executor.requests[0].command == "python3 solver.py"
    assert result.status == "completed"

    observation = started.import_result("run-001", result)
    assert observation is not None
    assert observation.metrics == {"auc_gap": 0.05}

    state = started.state("run-001")
    assert state.experiment_statuses["EXP-001"] == ExperimentStatus.COMPLETED
    assert state.loop_state == LoopState.PARSING

    record = FalsificationRecord(
        id="FR-001",
        hypothesis_id="H-001",
        observation_ids=[observation.id],
        strongest_alternative_explanation="fold size differences",
        confounders_checked=["fold size"],
        supporting_predictions_matched=["temporal CV score is lower than random CV"],
        contradicting_predictions_matched=[],
        disposition=FalsificationDisposition.SURVIVES,
    )
    started.record_falsification("run-001", record)

    update = belief_update(
        "H-001", 0.5, EvidenceLevel.STRONG_SUPPORT, "survives", [observation.id], VerifierResult.PASS
    )
    revised = started.record_belief_update("run-001", update, status=HypothesisStatus.SUPPORTED)
    assert revised.status == HypothesisStatus.SUPPORTED
    assert revised.current_confidence > 0.5
    assert observation.id in revised.evidence_for

    phase = started.advance_phase("run-001", PhaseEvidence(validation_locked=True))
    assert phase == Phase.DISCOVERY
    final = started.state("run-001")
    assert final.loop_state == LoopState.PLANNING
    assert final.hypotheses["H-001"].current_confidence == pytest.approx(update.posterior_confidence)


def test_observation_absorbs_sidecar_metrics(
    started: ResearchController, hypothesis: Hypothesis, proposal: ExperimentProposal, tmp_path: Path
) -> None:
    started.record_hypotheses("run-001", [hypothesis])
    started.record_proposals("run-001", [proposal])
    started.select_experiments("run-001", weights=WEIGHTS, size=1)
    _, result = _dispatch(started, StubExecutor())

    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "fold_metrics.json").write_text(json.dumps({"folds": [0.74, 0.76]}), encoding="utf-8")
    (artifacts / "seed_metrics.json").write_text(json.dumps([0.1, 0.2]), encoding="utf-8")

    observation = started.import_result("run-001", result, artifact_root=artifacts)
    assert observation is not None
    assert observation.fold_metrics == {"folds": [0.74, 0.76]}
    assert observation.seed_metrics == {"value": [0.1, 0.2]}
    assert observation.subgroup_metrics == {}


def test_failed_result_is_recorded_without_blocking_the_log(
    started: ResearchController, hypothesis: Hypothesis, proposal: ExperimentProposal
) -> None:
    started.record_hypotheses("run-001", [hypothesis])
    started.record_proposals("run-001", [proposal])
    started.select_experiments("run-001", weights=WEIGHTS, size=1)
    _, result = _dispatch(started, StubExecutor(status="failed"))
    observation = started.import_result("run-001", result)
    assert observation is not None
    assert observation.exit_status == "failed"
    assert started.state("run-001").experiment_statuses["EXP-001"] == ExperimentStatus.FAILED


def test_queued_results_are_not_imported(
    started: ResearchController, hypothesis: Hypothesis, proposal: ExperimentProposal
) -> None:
    started.record_hypotheses("run-001", [hypothesis])
    started.record_proposals("run-001", [proposal])
    started.select_experiments("run-001", weights=WEIGHTS, size=1)
    _, result = _dispatch(started, StubExecutor(status="queued"))
    assert started.import_result("run-001", result) is None
    assert started.state("run-001").experiment_statuses["EXP-001"] == ExperimentStatus.RUNNING


def test_gate_failures_become_recorded_rejections(
    started: ResearchController, hypothesis: Hypothesis, proposal: ExperimentProposal, clone_proposal
) -> None:
    started.record_hypotheses("run-001", [hypothesis])
    orphan = clone_proposal(proposal, id="EXP-ORPHAN", hypothesis_ids=["H-UNKNOWN"])
    started.record_proposals("run-001", [proposal, orphan])
    decision = started.select_experiments("run-001", weights=WEIGHTS, size=1)
    assert decision.selected_experiment_ids == ["EXP-001"]
    assert "EXP-ORPHAN" in decision.rejected_reasons
    assert started.state("run-001").experiment_statuses["EXP-ORPHAN"] == ExperimentStatus.REJECTED


def test_unselected_candidates_stay_available_for_the_next_round(
    started: ResearchController, hypothesis: Hypothesis, proposal: ExperimentProposal, clone_proposal
) -> None:
    started.record_hypotheses("run-001", [hypothesis])
    second = clone_proposal(proposal, id="EXP-002", novelty_score=0.1, lineage="other")
    started.record_proposals("run-001", [proposal, second])
    decision = started.select_experiments("run-001", weights=WEIGHTS, size=1)
    unselected = {"EXP-001", "EXP-002"} - set(decision.selected_experiment_ids)
    identifier = unselected.pop()
    assert identifier not in decision.rejected_reasons
    assert started.state("run-001").experiment_statuses[identifier] == ExperimentStatus.PROPOSED


def test_loop_steps_refuse_out_of_order_calls(
    started: ResearchController, hypothesis: Hypothesis, proposal: ExperimentProposal
) -> None:
    with pytest.raises(ValueError, match="no proposed experiments"):
        started.select_experiments("run-001", weights=WEIGHTS)

    started.record_hypotheses("run-001", [hypothesis])
    started.record_proposals("run-001", [proposal])
    with pytest.raises(LoopStateError, match="may not be dispatched"):
        _dispatch(started, StubExecutor())

    started.select_experiments("run-001", weights=WEIGHTS, size=1)
    with pytest.raises(ValueError, match="unknown experiment"):
        _dispatch(started, StubExecutor(), experiment_id="EXP-MISSING")


def test_proposals_are_validated_against_the_run(
    started: ResearchController, hypothesis: Hypothesis, proposal: ExperimentProposal, clone_proposal
) -> None:
    started.record_hypotheses("run-001", [hypothesis])
    started.record_proposals("run-001", [proposal])

    # A reused identifier costs that proposal, not the batch: the designs beside it are still good
    # research and dropping them ends the round for a naming accident.
    fresh = clone_proposal(proposal, id="EXP-FRESH")
    assert started.record_proposals("run-001", [proposal, fresh]) == ["EXP-FRESH"]
    with pytest.raises(ValueError, match="every proposed experiment reuses"):
        started.record_proposals("run-001", [proposal])

    foreign = clone_proposal(proposal, id="EXP-FOREIGN", run_id="other-run")
    with pytest.raises(ValueError, match="belongs to run other-run"):
        started.record_proposals("run-001", [foreign])


def test_hypothesis_limits_and_ownership_are_enforced(started: ResearchController, hypothesis: Hypothesis) -> None:
    foreign = hypothesis.model_copy(update={"id": "H-FOREIGN", "run_id": "other-run"})
    with pytest.raises(ValueError, match="belongs to run other-run"):
        started.record_hypotheses("run-001", [foreign])
    crowd = [hypothesis.model_copy(update={"id": f"H-{index:03d}"}) for index in range(4)]
    with pytest.raises(ValueError, match="maximum is 3"):
        started.record_hypotheses("run-001", crowd, max_active=3)


def test_second_batch_revises_a_known_hypothesis(started: ResearchController, hypothesis: Hypothesis) -> None:
    started.record_hypotheses("run-001", [hypothesis])
    revised = hypothesis.model_copy(update={"claim": "sharpened claim", "version": 2})
    started.record_hypotheses("run-001", [revised])
    assert started.state("run-001").hypotheses["H-001"].claim == "sharpened claim"


def test_falsification_and_belief_reject_unknown_references(
    started: ResearchController, hypothesis: Hypothesis
) -> None:
    started.record_hypotheses("run-001", [hypothesis])
    record = FalsificationRecord(
        id="FR-404",
        hypothesis_id="H-404",
        observation_ids=["OB-404"],
        strongest_alternative_explanation="none",
        confounders_checked=[],
        supporting_predictions_matched=[],
        contradicting_predictions_matched=[],
        disposition=FalsificationDisposition.INCONCLUSIVE,
    )
    with pytest.raises(ValueError, match="unknown hypothesis"):
        started.record_falsification("run-001", record)
    with pytest.raises(ValueError, match="unknown observations"):
        started.record_falsification("run-001", record.model_copy(update={"hypothesis_id": "H-001"}))
    update = belief_update("H-404", 0.5, EvidenceLevel.NEUTRAL, "none", ["OB-404"], VerifierResult.PASS)
    with pytest.raises(ValueError, match="unknown hypothesis"):
        started.record_belief_update("run-001", update)


def test_a_failed_hand_off_can_be_retried_under_a_new_attempt(
    started: ResearchController, hypothesis: Hypothesis, proposal: ExperimentProposal
) -> None:
    started.record_hypotheses("run-001", [hypothesis])
    started.record_proposals("run-001", [proposal])
    started.select_experiments("run-001", weights=WEIGHTS, size=1)
    _dispatch(started, StubExecutor())

    with pytest.raises(LoopStateError, match="may not be dispatched"):
        _dispatch(started, StubExecutor())

    retry = StubExecutor()
    request, _ = started.dispatch("run-001", "EXP-001", retry, container_image="research:1", attempt=2)
    assert request.idempotency_key == "run-001:EXP-001:attempt-2"
