from __future__ import annotations

from collections import Counter

from epistemic_loop.controller.phase_policy import PhaseEvidence
from epistemic_loop.controller.run_state import RunState
from epistemic_loop.domain.enums import (
    ExperimentStatus,
    ExperimentType,
    FailureClass,
    FalsificationDisposition,
    HypothesisStatus,
    HypothesisType,
    Phase,
)
from epistemic_loop.domain.models import Hypothesis, Observation

SETTLED_HYPOTHESIS_STATUSES = frozenset(
    {
        HypothesisStatus.SUPPORTED,
        HypothesisStatus.CONTESTED,
        HypothesisStatus.FALSIFIED,
        HypothesisStatus.RETIRED,
    }
)

SEARCH_SPACE_TYPES = frozenset(
    {
        HypothesisType.FEATURE_FAMILY,
        HypothesisType.MODEL_FAMILY,
        HypothesisType.REPRESENTATION,
        HypothesisType.ENSEMBLE_DIVERSITY,
        HypothesisType.CANDIDATE_GENERATION,
    }
)

COMPLETED = frozenset({ExperimentStatus.COMPLETED})


def _of_type(hypotheses: list[Hypothesis], kind: HypothesisType) -> list[Hypothesis]:
    return [item for item in hypotheses if item.type == kind]


def _spread(metrics: dict[str, object]) -> float:
    """Largest observed spread across any list of numbers in a fold/seed metric sidecar."""
    widest = 0.0
    for value in metrics.values():
        numbers = [float(item) for item in value if isinstance(item, (int, float))] if isinstance(value, list) else []
        if len(numbers) >= 2:
            widest = max(widest, max(numbers) - min(numbers))
    return widest


def _unstable(observation: Observation, threshold: float) -> bool:
    return _spread(observation.seed_metrics) > threshold or _spread(observation.fold_metrics) > threshold


def validation_locked(state: RunState) -> bool:
    """The working validation scheme counts as locked once a validation hypothesis survived a test.

    Locking is evidence, not a declaration: a supported `validation` hypothesis means some experiment
    preregistered a prediction about the split and the prediction held. An unresolved validation
    hypothesis therefore keeps the run in discovery, which is the intended behaviour.
    """
    validation = _of_type(list(state.hypotheses.values()), HypothesisType.VALIDATION)
    if not validation:
        return False
    if any(item.status in {HypothesisStatus.PROPOSED, HypothesisStatus.UNDER_TEST} for item in validation):
        return False
    return any(item.status == HypothesisStatus.SUPPORTED for item in validation)


def critical_leakage_resolved(state: RunState) -> bool:
    """Leakage must have been looked for and settled, not merely never raised."""
    leakage = _of_type(list(state.hypotheses.values()), HypothesisType.LEAKAGE)
    return bool(leakage) and all(item.status in SETTLED_HYPOTHESIS_STATUSES for item in leakage)


def stable_lineages(state: RunState, *, minimum_experiments: int = 2) -> int:
    """Lineages that produced repeated completed evidence rather than a single lucky number."""
    counts: Counter[str] = Counter()
    for identifier, proposal in state.proposals.items():
        if state.experiment_statuses.get(identifier) in COMPLETED:
            counts[proposal.lineage] += 1
    return sum(count >= minimum_experiments for count in counts.values())


def ablations_complete(state: RunState) -> bool:
    return any(
        proposal.experiment_type == ExperimentType.ABLATION and state.experiment_statuses.get(identifier) in COMPLETED
        for identifier, proposal in state.proposals.items()
    )


def search_space_defined(state: RunState) -> bool:
    return any(
        item.type in SEARCH_SPACE_TYPES and item.status == HypothesisStatus.SUPPORTED
        for item in state.hypotheses.values()
    )


def anomaly_detected(state: RunState, *, instability_threshold: float = 0.05) -> bool:
    """An exploitation result that contradicts what research concluded sends the run back.

    Three deterministic signals count: a hypothesis that carried supporting evidence and has since
    been contested or falsified, a model-class experiment failure, and a seed or fold spread wide
    enough that the reported gain cannot be distinguished from noise.
    """
    for item in state.hypotheses.values():
        if item.status in {HypothesisStatus.FALSIFIED, HypothesisStatus.CONTESTED} and item.evidence_for:
            return True
    for observation in state.observations.values():
        if observation.failure_class == FailureClass.MODEL:
            return True
        if _unstable(observation, instability_threshold):
            return True
    return any(
        record.disposition == FalsificationDisposition.FALSIFIED
        and state.hypotheses.get(record.hypothesis_id) is not None
        and state.hypotheses[record.hypothesis_id].evidence_for
        for record in state.falsifications.values()
    )


def derive_phase_evidence(state: RunState, *, instability_threshold: float = 0.05) -> PhaseEvidence:
    """Fold the event log into the evidence the phase policy consumes.

    Nothing here is asked of the model and nothing is passed in by hand: an unattended loop that
    cannot derive its own phase evidence stays in discovery forever, which is what happened before
    this function existed.
    """
    return PhaseEvidence(
        validation_locked=validation_locked(state),
        critical_leakage_resolved=critical_leakage_resolved(state),
        stable_lineages=stable_lineages(state),
        ablations_complete=ablations_complete(state),
        search_space_defined=search_space_defined(state),
        anomaly_detected=state.phase == Phase.EXPLOITATION
        and anomaly_detected(state, instability_threshold=instability_threshold),
    )
