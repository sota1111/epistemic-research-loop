from __future__ import annotations

from epistemic_loop.controller.phase_evidence import derive_phase_evidence
from epistemic_loop.controller.phase_policy import decide_phase
from epistemic_loop.controller.run_state import RunState
from epistemic_loop.domain.enums import (
    ExperimentStatus,
    ExperimentType,
    FailureClass,
    HypothesisStatus,
    HypothesisType,
    LoopState,
    Phase,
    RunStatus,
)
from epistemic_loop.domain.models import BudgetUsage, ExperimentProposal, Hypothesis, Observation, ResearchRun


def _run(phase: Phase = Phase.DISCOVERY) -> ResearchRun:
    return ResearchRun(
        id="run-001",
        competition_id="example",
        phase=phase,
        seed=1,
        status=RunStatus.RUNNING,
        base_commit_sha="abc123",
        dataset_fingerprint="f" * 64,
        config_hash="c" * 64,
    )


def _state(
    hypotheses: list[Hypothesis],
    proposals: dict[str, ExperimentProposal] | None = None,
    statuses: dict[str, ExperimentStatus] | None = None,
    observations: dict[str, Observation] | None = None,
    phase: Phase = Phase.DISCOVERY,
) -> RunState:
    return RunState(
        run=_run(phase),
        loop_state=LoopState.UPDATING,
        phase=phase,
        hypotheses={item.id: item for item in hypotheses},
        proposals=proposals or {},
        experiment_statuses=statuses or {},
        observations=observations or {},
        falsifications={},
        usage=BudgetUsage(),
        selection_order=(),
        violations=0,
    )


def _typed(hypothesis: Hypothesis, identifier: str, kind: HypothesisType, status: HypothesisStatus) -> Hypothesis:
    return hypothesis.model_copy(update={"id": identifier, "type": kind, "status": status, "version": 2})


def test_validation_is_not_locked_until_a_validation_hypothesis_survives(hypothesis: Hypothesis) -> None:
    proposed = _typed(hypothesis, "H-V", HypothesisType.VALIDATION, HypothesisStatus.UNDER_TEST)
    assert derive_phase_evidence(_state([proposed])).validation_locked is False

    supported = _typed(hypothesis, "H-V", HypothesisType.VALIDATION, HypothesisStatus.SUPPORTED)
    assert derive_phase_evidence(_state([supported])).validation_locked is True


def test_leakage_counts_as_resolved_only_when_it_was_actually_examined(hypothesis: Hypothesis) -> None:
    """Silence is not resolution: a run that never raised leakage has not ruled it out."""
    validation = _typed(hypothesis, "H-V", HypothesisType.VALIDATION, HypothesisStatus.SUPPORTED)
    assert derive_phase_evidence(_state([validation])).critical_leakage_resolved is False

    leakage = _typed(hypothesis, "H-L", HypothesisType.LEAKAGE, HypothesisStatus.FALSIFIED)
    assert derive_phase_evidence(_state([validation, leakage])).critical_leakage_resolved is True


def test_derived_evidence_moves_discovery_to_consolidation(hypothesis: Hypothesis) -> None:
    hypotheses = [
        _typed(hypothesis, "H-V", HypothesisType.VALIDATION, HypothesisStatus.SUPPORTED),
        _typed(hypothesis, "H-L", HypothesisType.LEAKAGE, HypothesisStatus.FALSIFIED),
        _typed(hypothesis, "H-T", HypothesisType.TEMPORAL_STRUCTURE, HypothesisStatus.SUPPORTED),
    ]
    confident = [item.model_copy(update={"current_confidence": 0.9, "version": 3}) for item in hypotheses]
    evidence = derive_phase_evidence(_state(confident))
    assert evidence.validation_locked and evidence.critical_leakage_resolved
    assert decide_phase(Phase.DISCOVERY, confident, evidence) == Phase.CONSOLIDATION


def test_ablations_and_lineage_stability_come_from_completed_experiments(
    hypothesis: Hypothesis,
    proposal: ExperimentProposal,
    clone_proposal,
) -> None:
    ablation = clone_proposal(proposal, id="EXP-AB", experiment_type=ExperimentType.ABLATION, lineage="gbdt")
    second = clone_proposal(proposal, id="EXP-AB2", lineage="gbdt")
    unfinished = clone_proposal(proposal, id="EXP-OPEN", lineage="ranker")
    state = _state(
        [hypothesis],
        proposals={item.id: item for item in (ablation, second, unfinished)},
        statuses={
            "EXP-AB": ExperimentStatus.COMPLETED,
            "EXP-AB2": ExperimentStatus.COMPLETED,
            "EXP-OPEN": ExperimentStatus.SELECTED,
        },
    )
    evidence = derive_phase_evidence(state)
    assert evidence.ablations_complete is True
    assert evidence.stable_lineages == 1, "only the lineage with two completed experiments is stable"


def _observation(**changes: object) -> Observation:
    payload: dict[str, object] = {
        "id": "OB-1",
        "experiment_id": "EXP-001",
        "run_id": "run-001",
        "code_commit_sha": "abc123",
        "environment_hash": "e" * 64,
        "dataset_fingerprint": "f" * 64,
        "exit_status": "completed",
    }
    payload.update(changes)
    return Observation.model_validate(payload)


def test_an_unstable_exploitation_result_returns_the_run_to_consolidation(hypothesis: Hypothesis) -> None:
    """A gain that moves 0.12 across seeds is noise; exploitation must not keep building on it."""
    unstable = _observation(seed_metrics={"auc": [0.70, 0.82]})
    state = _state([hypothesis], observations={"OB-1": unstable}, phase=Phase.EXPLOITATION)
    evidence = derive_phase_evidence(state)
    assert evidence.anomaly_detected is True
    assert decide_phase(Phase.EXPLOITATION, [hypothesis], evidence) == Phase.CONSOLIDATION


def test_a_model_failure_in_exploitation_is_an_anomaly(hypothesis: Hypothesis) -> None:
    failed = _observation(exit_status="failed", failure_class=FailureClass.MODEL)
    state = _state([hypothesis], observations={"OB-1": failed}, phase=Phase.EXPLOITATION)
    assert derive_phase_evidence(state).anomaly_detected is True


def test_anomalies_outside_exploitation_are_not_reported(hypothesis: Hypothesis) -> None:
    """Discovery is supposed to produce surprises; only exploitation treats one as a regression."""
    unstable = _observation(seed_metrics={"auc": [0.70, 0.82]})
    state = _state([hypothesis], observations={"OB-1": unstable}, phase=Phase.DISCOVERY)
    assert derive_phase_evidence(state).anomaly_detected is False
