from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from epistemic_loop.domain.enums import StructureClassification, StructureLifecycleState


@dataclass(frozen=True)
class SequentialFutilityDecision:
    stop_for_futility: bool
    repetitions: int
    null_gains_at_least_real: int
    posterior_probability_null_tail_below_five_percent: float
    reason: str | None


class MatchedNullSequentialFutilityRule:
    """Stop when a 95th-percentile null rejection has become implausible.

    Let ``p`` be the chance that one matched-null gain is at least the real
    gain. Passing the gate requires ``p < 0.05``. With a uniform Beta prior,
    futility fires when the posterior probability of that event is below the
    configured confidence. This rule must be preregistered before inspecting
    the next null repetition.
    """

    def __init__(
        self,
        *,
        target_tail_probability: float = 0.05,
        futility_confidence: float = 0.05,
        minimum_repetitions: int = 5,
    ):
        if not 0 < target_tail_probability < 1 or not 0 < futility_confidence < 1:
            raise ValueError("futility probabilities must lie strictly between zero and one")
        if minimum_repetitions < 1:
            raise ValueError("minimum_repetitions must be positive")
        self.target_tail_probability = target_tail_probability
        self.futility_confidence = futility_confidence
        self.minimum_repetitions = minimum_repetitions

    def assess(self, *, real_gain: float, matched_null_gains: Sequence[float]) -> SequentialFutilityDecision:
        count = len(matched_null_gains)
        exceedances = sum(item >= real_gain for item in matched_null_gains)
        probability = _integer_beta_cdf(
            self.target_tail_probability,
            alpha=exceedances + 1,
            beta=count - exceedances + 1,
        )
        stop = count >= self.minimum_repetitions and probability < self.futility_confidence
        return SequentialFutilityDecision(
            stop_for_futility=stop,
            repetitions=count,
            null_gains_at_least_real=exceedances,
            posterior_probability_null_tail_below_five_percent=probability,
            reason="structure_unsupported_by_matched_null" if stop else None,
        )


def _integer_beta_cdf(value: float, *, alpha: int, beta: int) -> float:
    """Regularized beta CDF for positive integer parameters without scipy."""

    total = alpha + beta - 1
    return sum(
        math.comb(total, index) * value**index * (1 - value) ** (total - index) for index in range(alpha, total + 1)
    )


@dataclass(frozen=True)
class StructureTerminalEvidence:
    null_rejected: bool
    independent_implication_reproduced: bool
    multi_context_multi_seed_reproduced: bool
    decision_improved: bool
    predictive_gain_reproduced: bool
    sufficient_power: bool = True


@dataclass(frozen=True)
class StructureTerminalDecision:
    lifecycle_state: StructureLifecycleState
    classification: StructureClassification | None
    structural_validity_passed: bool
    predictive_improvement_passed: bool
    reason: str


def decide_structure_terminal_state(evidence: StructureTerminalEvidence) -> StructureTerminalDecision:
    if not evidence.sufficient_power:
        return StructureTerminalDecision(
            lifecycle_state=StructureLifecycleState.INCONCLUSIVE,
            classification=None,
            structural_validity_passed=False,
            predictive_improvement_passed=evidence.predictive_gain_reproduced,
            reason="insufficient_power",
        )
    validity = (
        evidence.null_rejected
        and evidence.independent_implication_reproduced
        and evidence.multi_context_multi_seed_reproduced
    )
    if validity and evidence.decision_improved and evidence.predictive_gain_reproduced:
        return StructureTerminalDecision(
            StructureLifecycleState.VALIDATED_STRUCTURE,
            StructureClassification.VALIDATED_ACTIONABLE_STRUCTURE,
            True,
            True,
            "null_independent_implication_replication_and_adoption_passed",
        )
    if validity:
        return StructureTerminalDecision(
            StructureLifecycleState.STRUCTURALLY_PLAUSIBLE_NON_ACTIONABLE,
            StructureClassification.VALIDATED_NON_ACTIONABLE_STRUCTURE,
            True,
            False,
            "structural_validity_passed_without_decision_improvement",
        )
    if evidence.predictive_gain_reproduced:
        return StructureTerminalDecision(
            StructureLifecycleState.USEFUL_ENCODING_UNVALIDATED_STRUCTURE,
            StructureClassification.USEFUL_ENCODING_UNVALIDATED_STRUCTURE,
            False,
            True,
            "predictive_encoding_did_not_pass_structure_validation",
        )
    return StructureTerminalDecision(
        StructureLifecycleState.FALSIFIED,
        StructureClassification.REJECTED_STRUCTURE,
        False,
        False,
        "predictive_gain_not_reproduced",
    )
