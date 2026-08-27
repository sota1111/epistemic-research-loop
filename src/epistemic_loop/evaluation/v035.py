"""Independent-agent and blind-structure qualification metrics for v0.3.5."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from statistics import median

from epistemic_loop.controller.agent_qualification import PopulationQualificationScorecard


class V035Status(StrEnum):
    PASS = "pass"
    PARTIAL = "partial"
    FAIL = "fail"
    UNMEASURED = "unmeasured"


@dataclass(frozen=True)
class StructureValidationBundle:
    competing_hypotheses_registered: bool
    fold_causal_safety: bool
    confounder_preserving_null: bool
    independent_implication: bool
    multi_context_replication: bool
    negative_control_discrimination: bool
    decision_changed: bool

    @property
    def seed_evidence_passed(self) -> bool:
        """A seed is evidence only; terminal promotion is always aggregate-level."""

        return all(
            (
                self.competing_hypotheses_registered,
                self.fold_causal_safety,
                self.confounder_preserving_null,
                self.independent_implication,
                self.multi_context_replication,
                self.negative_control_discrimination,
                self.decision_changed,
            )
        )


@dataclass(frozen=True)
class SeedControlObservation:
    control_id: str
    seed: int
    structure_present: bool
    predicted_structure_probability: float
    selected_operator: str
    ground_truth_operator_match: bool
    bundle: StructureValidationBundle
    structure_free_sealed_auc: float
    structure_informed_sealed_auc: float

    def __post_init__(self) -> None:
        if not self.control_id.strip() or not self.selected_operator.strip():
            raise ValueError("control observations require opaque identifiers and an operator")
        if not 0 <= self.predicted_structure_probability <= 1:
            raise ValueError("structure confidence must lie in [0, 1]")
        if not 0 <= self.structure_free_sealed_auc <= 1:
            raise ValueError("structure-free AUC must lie in [0, 1]")
        if not 0 <= self.structure_informed_sealed_auc <= 1:
            raise ValueError("structure-informed AUC must lie in [0, 1]")

    @property
    def sealed_gain(self) -> float:
        return self.structure_informed_sealed_auc - self.structure_free_sealed_auc


@dataclass(frozen=True)
class LeaveOneSeedOutQualification:
    omitted_seed: int
    promoted: bool


@dataclass(frozen=True)
class ControlFamilyQualification:
    control_id: str
    structure_present: bool
    promoted: bool
    supporting_seeds: int
    evaluated_seeds: int
    leave_one_seed_out: tuple[LeaveOneSeedOutQualification, ...]
    decision_changed: bool
    ground_truth_operator_match: bool
    median_sealed_gain: float
    useful_structure: bool


@dataclass(frozen=True)
class ReliabilityBin:
    lower: float
    upper: float
    count: int
    mean_confidence: float
    empirical_frequency: float


@dataclass(frozen=True)
class StructureQualificationReport:
    families: tuple[ControlFamilyQualification, ...]
    true_structure_discovery_rate: float
    true_structure_rejection_rate: float
    false_structure_promotion_rate: float
    useful_structure_transfer_rate: float | None
    median_structure_sealed_gain: float | None
    brier_score: float
    expected_calibration_error: float
    reliability_diagram: tuple[ReliabilityBin, ...]
    discovery_gate_passed: bool
    rejection_gate_passed: bool
    transfer_gate_passed: bool

    @classmethod
    def evaluate(
        cls,
        observations: Sequence[SeedControlObservation],
        *,
        minimum_seeds: int = 3,
        minimum_support_fraction: float = 2 / 3,
    ) -> StructureQualificationReport:
        if not observations:
            raise ValueError("structure qualification requires control observations")
        grouped: dict[str, list[SeedControlObservation]] = defaultdict(list)
        for item in observations:
            grouped[item.control_id].append(item)
        families: list[ControlFamilyQualification] = []
        for control_id, values in sorted(grouped.items()):
            truth = {item.structure_present for item in values}
            seeds = {item.seed for item in values}
            if len(truth) != 1:
                raise ValueError(f"control truth changed across seeds: {control_id}")
            if len(values) < minimum_seeds or len(seeds) != len(values):
                raise ValueError(f"control family requires {minimum_seeds} unique seeds: {control_id}")
            supporting = sum(item.bundle.seed_evidence_passed for item in values)
            full_pass = supporting / len(values) >= minimum_support_fraction
            leave_one_out = tuple(
                LeaveOneSeedOutQualification(
                    omitted_seed=item.seed,
                    promoted=_support_fraction(
                        [other.bundle.seed_evidence_passed for other in values if other.seed != item.seed]
                    )
                    >= minimum_support_fraction,
                )
                for item in sorted(values, key=lambda value: value.seed)
            )
            promoted = full_pass and all(item.promoted for item in leave_one_out)
            gains = [item.sealed_gain for item in values]
            decision_changed = all(item.bundle.decision_changed for item in values)
            operator_match = all(item.ground_truth_operator_match for item in values)
            family_gain = median(gains)
            families.append(
                ControlFamilyQualification(
                    control_id=control_id,
                    structure_present=truth.pop(),
                    promoted=promoted,
                    supporting_seeds=supporting,
                    evaluated_seeds=len(values),
                    leave_one_seed_out=leave_one_out,
                    decision_changed=decision_changed,
                    ground_truth_operator_match=operator_match,
                    median_sealed_gain=family_gain,
                    useful_structure=(promoted and operator_match and decision_changed and family_gain > 0),
                )
            )

        positives = [item for item in families if item.structure_present]
        negatives = [item for item in families if not item.structure_present]
        if not positives or not negatives:
            raise ValueError("blind qualification requires positive and negative controls")
        discovered = sum(item.promoted and item.ground_truth_operator_match for item in positives)
        rejected = sum(not item.promoted for item in negatives)
        false_promotions = sum(item.promoted for item in negatives)
        actionable = [
            item for item in positives if item.promoted and item.ground_truth_operator_match and item.decision_changed
        ]
        useful = [item for item in actionable if item.useful_structure]
        transfer_rate = len(useful) / len(actionable) if actionable else None
        median_gain = median([item.median_sealed_gain for item in actionable]) if actionable else None
        predictions = [item.predicted_structure_probability for item in observations]
        outcomes = [item.structure_present for item in observations]
        brier = sum(
            (probability - float(outcome)) ** 2 for probability, outcome in zip(predictions, outcomes, strict=True)
        ) / len(predictions)
        diagram = _reliability_diagram(predictions, outcomes)
        calibration_error = sum(
            item.count / len(predictions) * abs(item.mean_confidence - item.empirical_frequency) for item in diagram
        )
        tsdr = discovered / len(positives)
        tsrr = rejected / len(negatives)
        fspr = false_promotions / len(negatives)
        return cls(
            families=tuple(families),
            true_structure_discovery_rate=tsdr,
            true_structure_rejection_rate=tsrr,
            false_structure_promotion_rate=fspr,
            useful_structure_transfer_rate=transfer_rate,
            median_structure_sealed_gain=median_gain,
            brier_score=brier,
            expected_calibration_error=calibration_error,
            reliability_diagram=diagram,
            discovery_gate_passed=tsdr >= 0.60,
            rejection_gate_passed=tsrr >= 0.80 and fspr <= 0.20,
            transfer_gate_passed=(
                transfer_rate is not None and transfer_rate >= 0.50 and median_gain is not None and median_gain > 0
            ),
        )


@dataclass(frozen=True)
class QualificationReliability:
    artifact_contract_completion: float
    oof_honesty: float
    sealed_isolation: float

    @property
    def passed(self) -> bool:
        return all(
            math.isclose(value, 1.0, abs_tol=1e-12)
            for value in (self.artifact_contract_completion, self.oof_honesty, self.sealed_isolation)
        )


@dataclass(frozen=True)
class V035Acceptance:
    independent_agent_diversity: V035Status
    evolution_and_exploration: V035Status
    structure_discovery: V035Status
    structure_rejection: V035Status
    structure_transfer: V035Status
    reliability: V035Status
    passed: bool

    @classmethod
    def assess(
        cls,
        population: PopulationQualificationScorecard,
        structures: StructureQualificationReport,
        reliability: QualificationReliability,
    ) -> V035Acceptance:
        diversity = population.diversity_gate_passed
        performance_improved = any(item.incumbent_improvements > 0 for item in population.agents)
        epistemic_completed = any(item.falsification_tests > 0 for item in population.agents)
        evolution = population.action_balance_gate_passed and performance_improved and epistemic_completed
        statuses = (
            V035Status.PASS if diversity else V035Status.FAIL,
            V035Status.PASS if evolution else V035Status.FAIL,
            V035Status.PASS if structures.discovery_gate_passed else V035Status.FAIL,
            V035Status.PASS if structures.rejection_gate_passed else V035Status.FAIL,
            V035Status.PASS if structures.transfer_gate_passed else V035Status.FAIL,
            V035Status.PASS if reliability.passed else V035Status.FAIL,
        )
        return cls(*statuses, passed=all(item is V035Status.PASS for item in statuses))


def _support_fraction(values: Sequence[bool]) -> float:
    return sum(values) / len(values) if values else 0.0


def _reliability_diagram(
    predictions: Sequence[float],
    outcomes: Sequence[bool],
    *,
    bins: int = 5,
) -> tuple[ReliabilityBin, ...]:
    grouped: list[list[tuple[float, bool]]] = [[] for _ in range(bins)]
    for probability, outcome in zip(predictions, outcomes, strict=True):
        index = min(int(probability * bins), bins - 1)
        grouped[index].append((probability, outcome))
    output: list[ReliabilityBin] = []
    for index, values in enumerate(grouped):
        if not values:
            continue
        output.append(
            ReliabilityBin(
                lower=index / bins,
                upper=(index + 1) / bins,
                count=len(values),
                mean_confidence=sum(item[0] for item in values) / len(values),
                empirical_frequency=sum(item[1] for item in values) / len(values),
            )
        )
    return tuple(output)
