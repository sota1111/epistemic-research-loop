from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

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


class SeedEvidenceDisposition(StrEnum):
    """A seed contributes evidence but can never make a terminal promotion."""

    SUPPORTING_EVIDENCE = "supporting_evidence"
    CONTRADICTING_EVIDENCE = "contradicting_evidence"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class SeedStructureEvidence:
    seed: int
    disposition: SeedEvidenceDisposition
    evidence_refs: tuple[str, ...] = ()


class ControlFamilyRole(StrEnum):
    THRESHOLD_TUNING = "threshold_tuning"
    HELD_OUT_EVALUATION = "held_out_evaluation"


@dataclass(frozen=True)
class StructureControlFamilyResult:
    family_id: str
    role: ControlFamilyRole
    structure_present: bool
    promoted: bool


@dataclass(frozen=True)
class LeaveOneSeedOutResult:
    omitted_seed: int
    passed: bool


@dataclass(frozen=True)
class StructurePromotionV2Decision:
    promoted: bool
    lifecycle_state: StructureLifecycleState
    leave_one_seed_out: tuple[LeaveOneSeedOutResult, ...]
    reasons: tuple[str, ...]


class StructurePromotionGateV2:
    """Aggregate-only promotion with leave-one-seed-out and blind controls."""

    def __init__(self, *, minimum_seeds: int = 3, minimum_support_fraction: float = 2 / 3):
        if minimum_seeds < 3:
            raise ValueError("v2 promotion requires at least three seeds")
        if not 0.5 < minimum_support_fraction <= 1:
            raise ValueError("minimum_support_fraction must be in (0.5, 1]")
        self.minimum_seeds = minimum_seeds
        self.minimum_support_fraction = minimum_support_fraction

    def assess(
        self,
        evidence: Sequence[SeedStructureEvidence],
        controls: Sequence[StructureControlFamilyResult],
    ) -> StructurePromotionV2Decision:
        reasons: list[str] = []
        if len({item.seed for item in evidence}) != len(evidence):
            raise ValueError("seed evidence must contain unique seeds")
        if len(evidence) < self.minimum_seeds:
            reasons.append("insufficient_seed_count")
        full_pass = self._aggregate_passes(evidence)
        if not full_pass:
            reasons.append("full_seed_aggregate_failed")
        leave_one_out = tuple(
            LeaveOneSeedOutResult(
                omitted_seed=item.seed,
                passed=self._aggregate_passes(tuple(other for other in evidence if other.seed != item.seed)),
            )
            for item in evidence
        )
        if not leave_one_out or not all(item.passed for item in leave_one_out):
            reasons.append("leave_one_seed_out_unstable")
        control_reasons = self._validate_controls(controls)
        reasons.extend(control_reasons)
        promoted = not reasons
        lifecycle = StructureLifecycleState.VALIDATED_STRUCTURE if promoted else StructureLifecycleState.INCONCLUSIVE
        return StructurePromotionV2Decision(promoted, lifecycle, leave_one_out, tuple(reasons))

    def _aggregate_passes(self, evidence: Sequence[SeedStructureEvidence]) -> bool:
        if not evidence:
            return False
        supporting = sum(item.disposition is SeedEvidenceDisposition.SUPPORTING_EVIDENCE for item in evidence)
        contradicting = sum(item.disposition is SeedEvidenceDisposition.CONTRADICTING_EVIDENCE for item in evidence)
        return contradicting == 0 and supporting / len(evidence) >= self.minimum_support_fraction

    @staticmethod
    def _validate_controls(controls: Sequence[StructureControlFamilyResult]) -> tuple[str, ...]:
        tuning_ids = {item.family_id for item in controls if item.role is ControlFamilyRole.THRESHOLD_TUNING}
        held_out = [item for item in controls if item.role is ControlFamilyRole.HELD_OUT_EVALUATION]
        reasons: list[str] = []
        if tuning_ids & {item.family_id for item in held_out}:
            reasons.append("control_family_reused_after_threshold_tuning")
        if not any(item.structure_present for item in held_out):
            reasons.append("held_out_positive_control_missing")
        if not any(not item.structure_present for item in held_out):
            reasons.append("held_out_negative_control_missing")
        if any(item.structure_present and not item.promoted for item in held_out):
            reasons.append("held_out_positive_control_not_promoted")
        if any(not item.structure_present and item.promoted for item in held_out):
            reasons.append("held_out_negative_control_false_promotion")
        return tuple(reasons)
