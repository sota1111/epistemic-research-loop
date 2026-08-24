from __future__ import annotations

from pathlib import Path

import pytest

from epistemic_loop.controller.run_state import load_run_state
from epistemic_loop.domain.enums import ExperimentStatus, ExperimentType, Phase, RunStatus
from epistemic_loop.domain.events import EventType
from epistemic_loop.domain.models import (
    DecisionRecord,
    ExperimentProposal,
    Hypothesis,
    Observation,
    ResearchRun,
)
from epistemic_loop.domain.validation import experiment_fingerprint
from epistemic_loop.holdout.violations import HoldoutViolation
from epistemic_loop.storage.repositories import ResearchRepository


@pytest.fixture
def repository(tmp_path: Path) -> ResearchRepository:
    return ResearchRepository(tmp_path / ".runs", tmp_path / "projection.db")


@pytest.fixture
def run() -> ResearchRun:
    return ResearchRun(
        id="run-001",
        competition_id="example",
        seed=7,
        base_commit_sha="abc123",
        dataset_fingerprint="f" * 64,
        config_hash="c" * 64,
    )


def _state(repository: ResearchRepository):
    return load_run_state(repository.event_store("run-001").read_all())


def test_missing_run_created_event_is_an_error() -> None:
    with pytest.raises(ValueError, match="does not contain a RunCreated event"):
        load_run_state([])


def test_only_settled_experiments_block_duplicates(
    repository: ResearchRepository, run: ResearchRun, proposal: ExperimentProposal, clone_proposal
) -> None:
    second = clone_proposal(proposal, id="EXP-002")
    repository.append("run-001", EventType.RUN_CREATED, run)
    repository.append("run-001", EventType.EXPERIMENT_PROPOSED, proposal)
    repository.append("run-001", EventType.EXPERIMENT_PROPOSED, second)

    assert _state(repository).settled_fingerprints() == frozenset()

    decision = DecisionRecord(
        id="DR-001",
        run_id="run-001",
        candidate_experiment_ids=["EXP-001", "EXP-002"],
        utility_breakdown={},
        selected_experiment_ids=["EXP-001"],
        rejected_reasons={"EXP-002": ["duplicate"]},
        phase=Phase.DISCOVERY,
        remaining_budget={},
        policy_version="selection/v1",
    )
    repository.append("run-001", EventType.EXPERIMENT_SELECTED, decision)

    state = _state(repository)
    assert state.settled_fingerprints() == frozenset({experiment_fingerprint(proposal)})
    assert state.experiment_statuses["EXP-002"] == ExperimentStatus.REJECTED
    assert state.usage.experiments == 1
    assert state.usage.cpu_hours == pytest.approx(1.0)
    assert [item.id for item in state.open_candidates()] == []


def test_selection_order_drives_the_consecutive_optimization_window(
    repository: ResearchRepository, run: ResearchRun, proposal: ExperimentProposal, clone_proposal
) -> None:
    repository.append("run-001", EventType.RUN_CREATED, run)
    identifiers = []
    for index in range(4):
        candidate = clone_proposal(
            proposal,
            id=f"EXP-{index:03d}",
            experiment_type=ExperimentType.OPTIMIZATION.value,
        )
        identifiers.append(candidate.id)
        repository.append("run-001", EventType.EXPERIMENT_PROPOSED, candidate)
        repository.append(
            "run-001",
            EventType.EXPERIMENT_SELECTED,
            DecisionRecord(
                id=f"DR-{index:03d}",
                run_id="run-001",
                candidate_experiment_ids=[candidate.id],
                utility_breakdown={},
                selected_experiment_ids=[candidate.id],
                rejected_reasons={},
                phase=Phase.DISCOVERY,
                remaining_budget={},
                policy_version="selection/v1",
            ),
        )
    state = _state(repository)
    assert state.selection_order == tuple(identifiers)
    assert state.recent_experiment_types() == (ExperimentType.OPTIMIZATION,) * 3
    assert state.gate_context().recent_experiment_types == (ExperimentType.OPTIMIZATION,) * 3


def test_lifecycle_events_and_observations_are_folded(
    repository: ResearchRepository, run: ResearchRun, proposal: ExperimentProposal
) -> None:
    repository.append("run-001", EventType.RUN_CREATED, run)
    repository.append("run-001", EventType.EXPERIMENT_PROPOSED, proposal)
    repository.append("run-001", EventType.EXPERIMENT_STARTED, {"experiment_id": "EXP-001"})
    assert _state(repository).experiment_statuses["EXP-001"] == ExperimentStatus.RUNNING

    observation = Observation(
        id="OB-001",
        experiment_id="EXP-001",
        run_id="run-001",
        metrics={"auc_gap": 0.05},
        code_commit_sha="abc123",
        environment_hash="env",
        dataset_fingerprint="data",
        exit_status="completed",
    )
    repository.append("run-001", EventType.OBSERVATION_RECORDED, observation)
    repository.append("run-001", EventType.EXPERIMENT_COMPLETED, {"experiment_id": "EXP-001"})

    state = _state(repository)
    assert state.experiment_statuses["EXP-001"] == ExperimentStatus.COMPLETED
    assert [item.id for item in state.observations_for("EXP-001")] == ["OB-001"]
    assert state.observations_for("EXP-404") == []
    assert [item.id for item in state.experiments_with_status(ExperimentStatus.COMPLETED)] == ["EXP-001"]


def test_phase_and_status_track_recorded_events(
    repository: ResearchRepository, run: ResearchRun, hypothesis: Hypothesis
) -> None:
    repository.append("run-001", EventType.RUN_CREATED, run)
    repository.append("run-001", EventType.HYPOTHESIS_PROPOSED, hypothesis)
    repository.append("run-001", EventType.STATE_CHANGED, {"state": "observing", "run_status": "running"})
    repository.append("run-001", EventType.PHASE_CHANGED, {"phase": Phase.CONSOLIDATION.value})

    state = _state(repository)
    assert state.run.status == RunStatus.RUNNING
    assert state.phase == Phase.CONSOLIDATION
    assert state.run_id == "run-001"

    repository.append(
        "run-001",
        EventType.VIOLATION_DETECTED,
        HoldoutViolation(run_id="run-001", code="X", description="d", actor="agent"),
    )
    blocked = _state(repository)
    assert blocked.violations == 1
    assert blocked.run.status == RunStatus.BLOCKED

    repository.append("run-001", EventType.RUN_FINALIZED, {"run_id": "run-001"})
    finalized = _state(repository)
    assert finalized.phase == Phase.FINALIZED
    assert finalized.run.status == RunStatus.COMPLETED


def test_belief_updates_move_confidence_without_a_revision_event(
    repository: ResearchRepository, run: ResearchRun, hypothesis: Hypothesis
) -> None:
    repository.append("run-001", EventType.RUN_CREATED, run)
    repository.append("run-001", EventType.HYPOTHESIS_PROPOSED, hypothesis)
    repository.append(
        "run-001",
        EventType.BELIEF_UPDATED,
        {
            "id": "BU-001",
            "hypothesis_id": "H-001",
            "prior_confidence": 0.5,
            "posterior_confidence": 0.62,
            "update_method": "log_odds_evidence",
            "evidence_strength": 0.5,
            "evidence_summary": "survives",
            "observation_ids": ["OB-001"],
            "verifier_result": "pass",
        },
    )
    state = _state(repository)
    assert state.hypotheses["H-001"].current_confidence == pytest.approx(0.62)
    assert state.hypotheses["H-001"].version == 2


def test_observed_runtime_exposes_the_gap_between_estimate_and_actual(
    repository: ResearchRepository,
    run: ResearchRun,
    proposal: ExperimentProposal,
    clone_proposal,
) -> None:
    """Budgets are spent against declared estimates, and nothing ever checked them.

    An experiment that estimates a fraction of what it costs still passes every budget gate, so a
    run can consume several times its nominal compute unnoticed -- and two runs compared "at the
    same budget" can differ by a large factor in what they actually used.
    """
    from epistemic_loop.domain.models import CostEstimate, DecisionRecord, Observation

    repository.append("run-001", EventType.RUN_CREATED, run)
    cheap_looking = clone_proposal(proposal, estimated_cost=CostEstimate(cpu_hours=1.0, wall_hours=0.05).model_dump())
    repository.append("run-001", EventType.EXPERIMENT_PROPOSED, cheap_looking)
    repository.append(
        "run-001",
        EventType.EXPERIMENT_SELECTED,
        DecisionRecord(
            id="DR-1",
            run_id="run-001",
            candidate_experiment_ids=["EXP-001"],
            utility_breakdown={},
            selected_experiment_ids=["EXP-001"],
            rejected_reasons={},
            phase=Phase.DISCOVERY,
            remaining_budget={},
            policy_version="selection/v1",
        ),
    )
    repository.append(
        "run-001",
        EventType.OBSERVATION_RECORDED,
        Observation(
            id="OB-1",
            experiment_id="EXP-001",
            run_id="run-001",
            code_commit_sha="abc123",
            environment_hash="e" * 64,
            dataset_fingerprint="f" * 64,
            exit_status="completed",
            runtime={"wall_seconds": 540.0},  # 0.15 h against a declared 0.05 h
        ),
    )

    observed = _state(repository).observed_runtime()

    assert observed["estimated_wall_hours"] == 0.05
    assert observed["wall_hours"] == 0.15
    assert observed["estimate_ratio"] == 3.0, "the run spent three times what its gate charged it"
    assert observed["experiments_observed"] == 1
