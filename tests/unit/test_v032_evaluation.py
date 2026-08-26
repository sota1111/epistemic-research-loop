from __future__ import annotations

import pytest

from epistemic_loop.evaluation.acceptance import AcceptanceStatus
from epistemic_loop.evaluation.v032 import (
    ArmBudgetLedger,
    CandidateEligibility,
    CandidateEligibilityEvidence,
    DebtStatus,
    MatchedBudgetAssessment,
    PredictiveDiversityDebtBreakdown,
    SystemArm,
    SystemArmCapabilities,
    V032Acceptance,
)


def test_predictive_debt_is_split_without_hiding_low_archive_breadth() -> None:
    debt = PredictiveDiversityDebtBreakdown.assess(
        quality_floor_passed=True,
        lower_archive_correlation=True,
        positive_nested_auc_gain=True,
        residual_effective_rank=1.116561,
    )

    assert debt.quality_complementary_candidate.status is DebtStatus.RESOLVED
    assert debt.archive_wide_predictive_breadth.status is DebtStatus.PARTIAL
    assert debt.hidden_transfer.status is DebtStatus.UNMEASURED


def test_hidden_transfer_closes_only_for_positive_private_gain() -> None:
    debt = PredictiveDiversityDebtBreakdown.assess(
        quality_floor_passed=True,
        lower_archive_correlation=True,
        positive_nested_auc_gain=True,
        residual_effective_rank=1.3,
        candidate_private_auc=0.91,
        ensemble_private_auc=0.92,
        archive_best_private_auc=0.90,
    )
    assert debt.hidden_transfer.status is DebtStatus.RESOLVED


def test_standalone_and_ensemble_eligibility_are_independent() -> None:
    evidence = CandidateEligibilityEvidence(
        artifact_contract_passed=True,
        leakage_check_passed=True,
        oof_honesty_passed=True,
        mean_auc=0.87,
        quality_floor=0.88,
        seed_standard_deviation=0.005,
        stability_threshold=0.01,
        nested_leave_one_out_auc_gain=0.002,
        positive_gain_horizons=3,
        evaluated_horizons=3,
        maximum_fold_weight=0.55,
    )
    eligibility = CandidateEligibility.assess(evidence)
    assert eligibility.standalone is False
    assert eligibility.ensemble is True
    assert eligibility.standalone_failures == ("standalone_quality",)


def test_unstable_candidate_fails_both_archives() -> None:
    evidence = CandidateEligibilityEvidence(True, True, True, 0.91, 0.88, 0.02514, 0.01, 0.01, 3, 3, 0.5)
    eligibility = CandidateEligibility.assess(evidence)
    assert not eligibility.standalone
    assert not eligibility.ensemble
    assert "seed_stability" in eligibility.ensemble_failures


def _ledger(arm: SystemArm, *, wall: float = 72.0) -> ArmBudgetLedger:
    return ArmBudgetLedger(arm, 100_000, 240, 0, wall, 60, 12, 60 if arm is SystemArm.C else 0)


def test_system_arm_switch_only_enables_epistemic_layer_for_c() -> None:
    assert not SystemArmCapabilities.for_arm(SystemArm.B).predictive_diversity_debt
    assert SystemArmCapabilities.for_arm(SystemArm.B_PLUS).predictive_diversity_debt
    assert not SystemArmCapabilities.for_arm(SystemArm.B_PLUS).hypothesis_registry
    assert SystemArmCapabilities.for_arm(SystemArm.C).falsifier
    assert _ledger(SystemArm.C).opportunity_cost_fraction == pytest.approx(60 / 72)


def test_matched_budget_requires_wall_clock_as_well_as_compute() -> None:
    ledgers = (_ledger(SystemArm.B), _ledger(SystemArm.B_PLUS), _ledger(SystemArm.C))
    assert MatchedBudgetAssessment.assess(ledgers).matched
    mismatched = (ledgers[0], _ledger(SystemArm.B_PLUS, wall=60), ledgers[2])
    assert MatchedBudgetAssessment.assess(mismatched).mismatches == ("wall_clock_minutes",)


def test_v032_acceptance_preserves_unmeasured_claims() -> None:
    debt = PredictiveDiversityDebtBreakdown.assess(
        quality_floor_passed=True,
        lower_archive_correlation=True,
        positive_nested_auc_gain=True,
        residual_effective_rank=1.116561,
    )
    acceptance = V032Acceptance.from_evidence(
        debt=debt,
        primary_hidden_endpoint_passed=None,
        true_structure_discovery_passed=None,
        matched_budget_ablation_passed=None,
    )
    assert acceptance.quality_conditioned_predictive_diversity is AcceptanceStatus.PASS
    assert acceptance.archive_wide_predictive_breadth is AcceptanceStatus.PARTIAL_PASS
    assert acceptance.primary_hidden_endpoint is AcceptanceStatus.UNMEASURED
