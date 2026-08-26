"""v0.3.2 acceptance, eligibility, and matched-budget contracts.

These contracts refine measurement without changing the v0.3.1 control plane.
They deliberately separate local candidate complementarity, archive breadth,
and hidden transfer, and separate standalone quality from population value.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from epistemic_loop.evaluation.acceptance import AcceptanceStatus


class DebtStatus(StrEnum):
    OPEN = "open"
    PARTIAL = "partial"
    RESOLVED = "resolved"
    UNMEASURED = "unmeasured"


@dataclass(frozen=True)
class PredictiveDiversityDebtItem:
    debt_id: str
    name: str
    status: DebtStatus
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class PredictiveDiversityDebtBreakdown:
    quality_complementary_candidate: PredictiveDiversityDebtItem
    archive_wide_predictive_breadth: PredictiveDiversityDebtItem
    hidden_transfer: PredictiveDiversityDebtItem

    @classmethod
    def assess(
        cls,
        *,
        quality_floor_passed: bool,
        lower_archive_correlation: bool,
        positive_nested_auc_gain: bool,
        residual_effective_rank: float,
        breadth_threshold: float = 1.2,
        candidate_private_auc: float | None = None,
        ensemble_private_auc: float | None = None,
        archive_best_private_auc: float | None = None,
    ) -> PredictiveDiversityDebtBreakdown:
        pd1_passed = quality_floor_passed and (lower_archive_correlation or positive_nested_auc_gain)
        pd1 = PredictiveDiversityDebtItem(
            "PD-1",
            "quality_complementary_candidate",
            DebtStatus.RESOLVED if pd1_passed else DebtStatus.OPEN,
            tuple(
                name
                for name, passed in {
                    "quality_floor_passed": quality_floor_passed,
                    "lower_archive_residual_correlation": lower_archive_correlation,
                    "positive_nested_auc_gain": positive_nested_auc_gain,
                }.items()
                if passed
            ),
        )
        breadth_passed = residual_effective_rank >= breadth_threshold
        pd2 = PredictiveDiversityDebtItem(
            "PD-2",
            "archive_wide_predictive_breadth",
            DebtStatus.RESOLVED if breadth_passed else DebtStatus.PARTIAL,
            (f"residual_effective_rank={residual_effective_rank:.6f}", f"pilot_threshold={breadth_threshold:.6f}"),
        )
        if candidate_private_auc is None or ensemble_private_auc is None or archive_best_private_auc is None:
            pd3_status = DebtStatus.UNMEASURED
            pd3_evidence: tuple[str, ...] = ("hidden_or_private_scores_missing",)
        else:
            single_gain = candidate_private_auc - archive_best_private_auc
            ensemble_gain = ensemble_private_auc - archive_best_private_auc
            pd3_status = DebtStatus.RESOLVED if max(single_gain, ensemble_gain) > 0 else DebtStatus.OPEN
            pd3_evidence = (
                f"single_private_gain={single_gain:.6f}",
                f"ensemble_private_gain={ensemble_gain:.6f}",
            )
        return cls(pd1, pd2, PredictiveDiversityDebtItem("PD-3", "hidden_transfer", pd3_status, pd3_evidence))


@dataclass(frozen=True)
class CandidateEligibilityEvidence:
    artifact_contract_passed: bool
    leakage_check_passed: bool
    oof_honesty_passed: bool
    mean_auc: float
    quality_floor: float
    seed_standard_deviation: float
    stability_threshold: float
    nested_leave_one_out_auc_gain: float
    positive_gain_horizons: int
    evaluated_horizons: int
    maximum_fold_weight: float
    maximum_allowed_fold_weight: float = 0.8


@dataclass(frozen=True)
class CandidateEligibility:
    standalone: bool
    ensemble: bool
    standalone_failures: tuple[str, ...]
    ensemble_failures: tuple[str, ...]

    @classmethod
    def assess(cls, evidence: CandidateEligibilityEvidence) -> CandidateEligibility:
        common = {
            "artifact_contract": evidence.artifact_contract_passed,
            "leakage_check": evidence.leakage_check_passed,
            "oof_honesty": evidence.oof_honesty_passed,
            "seed_stability": evidence.seed_standard_deviation <= evidence.stability_threshold,
        }
        standalone_checks = {
            **common,
            "standalone_quality": evidence.mean_auc >= evidence.quality_floor,
        }
        required_positive_horizons = max(2, (evidence.evaluated_horizons + 1) // 2)
        ensemble_checks = {
            **common,
            "positive_leave_one_out_gain": evidence.nested_leave_one_out_auc_gain > 0,
            "multi_horizon_gain_stability": evidence.positive_gain_horizons >= required_positive_horizons,
            "weight_not_fold_concentrated": evidence.maximum_fold_weight <= evidence.maximum_allowed_fold_weight,
        }
        return cls(
            standalone=all(standalone_checks.values()),
            ensemble=all(ensemble_checks.values()),
            standalone_failures=tuple(name for name, passed in standalone_checks.items() if not passed),
            ensemble_failures=tuple(name for name, passed in ensemble_checks.items() if not passed),
        )


class SystemArm(StrEnum):
    B = "B"
    B_PLUS = "B_plus"
    C = "C"


@dataclass(frozen=True)
class SystemArmCapabilities:
    hypothesis_registry: bool
    structural_maturation: bool
    falsifier: bool
    predictive_slice_preregistration: bool
    predictive_diversity_debt: bool

    @classmethod
    def for_arm(cls, arm: SystemArm) -> SystemArmCapabilities:
        return cls(
            hypothesis_registry=arm is SystemArm.C,
            structural_maturation=arm is SystemArm.C,
            falsifier=arm is SystemArm.C,
            predictive_slice_preregistration=arm in {SystemArm.B_PLUS, SystemArm.C},
            predictive_diversity_debt=arm in {SystemArm.B_PLUS, SystemArm.C},
        )


@dataclass(frozen=True)
class ArmBudgetLedger:
    arm: SystemArm
    token_count: int
    cpu_minutes: float
    gpu_minutes: float
    wall_clock_minutes: float
    heavy_compute_minutes: float
    candidate_compute_minutes: float
    falsification_compute_minutes: float

    @property
    def opportunity_cost_fraction(self) -> float:
        total = self.candidate_compute_minutes + self.falsification_compute_minutes
        return self.falsification_compute_minutes / total if total > 0 else 0.0


@dataclass(frozen=True)
class MatchedBudgetAssessment:
    matched: bool
    mismatches: tuple[str, ...]

    @classmethod
    def assess(
        cls,
        ledgers: tuple[ArmBudgetLedger, ...],
        *,
        relative_tolerance: float = 0.01,
    ) -> MatchedBudgetAssessment:
        if {ledger.arm for ledger in ledgers} != {SystemArm.B, SystemArm.B_PLUS, SystemArm.C}:
            return cls(False, ("arms_must_be_exactly_B_B_plus_C",))
        fields = ("token_count", "cpu_minutes", "gpu_minutes", "wall_clock_minutes", "heavy_compute_minutes")
        mismatches: list[str] = []
        for field in fields:
            values = [float(getattr(ledger, field)) for ledger in ledgers]
            scale = max(max(values), 1.0)
            if max(values) - min(values) > relative_tolerance * scale:
                mismatches.append(field)
        return cls(not mismatches, tuple(mismatches))


@dataclass(frozen=True)
class V032Acceptance:
    control_plane: AcceptanceStatus
    artifact_reliability: AcceptanceStatus
    full_common_crossfit: AcceptanceStatus
    generic_semantic_diversity: AcceptanceStatus
    quality_conditioned_predictive_diversity: AcceptanceStatus
    archive_wide_predictive_breadth: AcceptanceStatus
    structural_falsification: AcceptanceStatus
    true_structure_discovery: AcceptanceStatus
    incremental_value_over_strong_qd: AcceptanceStatus
    primary_hidden_endpoint: AcceptanceStatus

    @classmethod
    def from_evidence(
        cls,
        *,
        debt: PredictiveDiversityDebtBreakdown,
        primary_hidden_endpoint_passed: bool | None | AcceptanceStatus,
        true_structure_discovery_passed: bool | None | AcceptanceStatus,
        matched_budget_ablation_passed: bool | None | AcceptanceStatus,
    ) -> V032Acceptance:
        return cls(
            control_plane=AcceptanceStatus.PASS,
            artifact_reliability=AcceptanceStatus.PASS,
            full_common_crossfit=AcceptanceStatus.PASS,
            generic_semantic_diversity=AcceptanceStatus.PASS,
            quality_conditioned_predictive_diversity=(
                AcceptanceStatus.PASS
                if debt.quality_complementary_candidate.status is DebtStatus.RESOLVED
                else AcceptanceStatus.FAIL
            ),
            archive_wide_predictive_breadth=(
                AcceptanceStatus.PASS
                if debt.archive_wide_predictive_breadth.status is DebtStatus.RESOLVED
                else AcceptanceStatus.PARTIAL_PASS
            ),
            structural_falsification=AcceptanceStatus.PASS,
            true_structure_discovery=_optional_acceptance(true_structure_discovery_passed),
            incremental_value_over_strong_qd=_optional_acceptance(matched_budget_ablation_passed),
            primary_hidden_endpoint=_optional_acceptance(primary_hidden_endpoint_passed),
        )


def _optional_acceptance(passed: bool | None | AcceptanceStatus) -> AcceptanceStatus:
    if isinstance(passed, AcceptanceStatus):
        return passed
    if passed is None:
        return AcceptanceStatus.UNMEASURED
    return AcceptanceStatus.PASS if passed else AcceptanceStatus.FAIL
