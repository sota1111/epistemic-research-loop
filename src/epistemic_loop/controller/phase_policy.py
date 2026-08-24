from __future__ import annotations

from dataclasses import dataclass

from epistemic_loop.domain.enums import Consequence, HypothesisStatus, Phase
from epistemic_loop.domain.models import Hypothesis


@dataclass(frozen=True)
class PhaseEvidence:
    validation_locked: bool = False
    critical_leakage_resolved: bool = False
    stable_lineages: int = 0
    ablations_complete: bool = False
    search_space_defined: bool = False
    anomaly_detected: bool = False


def decide_phase(
    current: Phase,
    hypotheses: list[Hypothesis],
    evidence: PhaseEvidence,
    *,
    uncertainty_threshold: float = 0.35,
) -> Phase:
    if evidence.anomaly_detected and current == Phase.EXPLOITATION:
        return Phase.CONSOLIDATION
    active = [item for item in hypotheses if item.status not in {HypothesisStatus.RETIRED, HypothesisStatus.FALSIFIED}]
    mean_uncertainty = sum(1 - abs(2 * item.current_confidence - 1) for item in active) / len(active) if active else 1.0
    high_impact_tested = sum(
        item.downstream_consequence in {Consequence.HIGH, Consequence.CRITICAL}
        and item.status
        in {
            HypothesisStatus.SUPPORTED,
            HypothesisStatus.CONTESTED,
            HypothesisStatus.FALSIFIED,
        }
        for item in hypotheses
    )
    if current == Phase.DISCOVERY:
        if (
            evidence.validation_locked
            and evidence.critical_leakage_resolved
            and high_impact_tested >= 3
            and mean_uncertainty <= uncertainty_threshold
        ):
            return Phase.CONSOLIDATION
    elif (
        current == Phase.CONSOLIDATION
        and evidence.stable_lineages >= 1
        and evidence.ablations_complete
        and evidence.search_space_defined
    ):
        return Phase.EXPLOITATION
    return current
