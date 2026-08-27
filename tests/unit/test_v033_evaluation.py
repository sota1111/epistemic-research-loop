from __future__ import annotations

from dataclasses import replace

import pytest

from epistemic_loop.evaluation.acceptance import AcceptanceStatus
from epistemic_loop.evaluation.v032 import SystemArm
from epistemic_loop.evaluation.v033 import (
    AblationOutputLock,
    ArchiveBreadthAssessment,
    ComponentEffectObservation,
    ComponentEffectPrediction,
    EffectSign,
    MechanismCalibration,
    PrivateResultUse,
    SealedAblationBatch,
    V033Acceptance,
    VerificationStatus,
    assert_private_result_use_allowed,
    evaluate_sealed_private_batch,
)


def test_v033_acceptance_does_not_widen_v032_hidden_claim() -> None:
    result = V033Acceptance.from_v032_observations()

    assert result.locked_portfolio_gain_vs_previous_archive is AcceptanceStatus.PASS
    assert result.w02_standalone_hidden_transfer is AcceptanceStatus.FAIL
    assert result.ensemble_hidden_transfer is AcceptanceStatus.PASS
    assert result.local_candidate_ranking_fidelity is AcceptanceStatus.PARTIAL_PASS
    assert result.system_c_vs_b is AcceptanceStatus.UNMEASURED
    assert result.system_c_vs_b_plus is AcceptanceStatus.UNMEASURED


def test_effective_rank_is_diagnostic_and_nonblocking() -> None:
    breadth = ArchiveBreadthAssessment.assess(1.116561)

    assert breadth.status is VerificationStatus.PARTIAL
    assert breadth.blocking is False
    assert breadth.purpose == "diagnostic_only"
    assert ArchiveBreadthAssessment.assess(1.2).status is VerificationStatus.PASS


def test_mechanism_calibration_detects_right_sign_but_wrong_dominant_driver() -> None:
    predictions = (
        ComponentEffectPrediction("topology", EffectSign.POSITIVE, 0.001, 0.01, 1, ("identity_absent",), True),
        ComponentEffectPrediction("category_hash", EffectSign.POSITIVE, 0.001, 0.01, 2, ("all_oof",), True),
    )
    observations = (
        ComponentEffectObservation("topology", 0.002025, 2, ("identity_absent",), True),
        ComponentEffectObservation("category_hash", 0.023077, 1, ("all_oof",), True),
    )

    calibration = MechanismCalibration.assess(predictions, observations)

    assert calibration.status is VerificationStatus.PARTIAL
    assert calibration.sign_accuracy == 1.0
    assert calibration.rank_accuracy == 0.0
    assert "category_hash:range" in calibration.mismatches


def test_mechanism_predictions_validate_inputs_and_empty_is_unmeasured() -> None:
    with pytest.raises(ValueError, match="minimum_effect"):
        ComponentEffectPrediction("x", EffectSign.POSITIVE, 1, 0, 1, (), True)
    with pytest.raises(ValueError, match="importance"):
        ComponentEffectPrediction("x", EffectSign.POSITIVE, 0, 1, 0, (), True)
    assert MechanismCalibration.assess((), ()).status is VerificationStatus.UNMEASURED
    prediction = (ComponentEffectPrediction("x", EffectSign.NEUTRAL, -0.1, 0.1, 1, ("all",), False),)
    with pytest.raises(ValueError, match="identical"):
        MechanismCalibration.assess(prediction, ())


def _locks(seeds: tuple[int, ...] = tuple(range(12))) -> list[AblationOutputLock]:
    digest = "a" * 64
    return [
        AblationOutputLock(
            output_id=f"{arm.value}-{seed}",
            arm=arm,
            seed=seed,
            candidate_commit=digest,
            feature_manifest_sha256=digest,
            fold_plan_sha256=digest,
            selection_rule_sha256=digest,
            test_prediction_sha256=digest,
            submission_sha256=digest,
        )
        for arm in (SystemArm.B, SystemArm.B_PLUS, SystemArm.C)
        for seed in seeds
    ]


def _batch() -> SealedAblationBatch:
    return SealedAblationBatch.freeze(
        _locks(),
        policy_sha256="1" * 64,
        prompt_sha256="2" * 64,
        budget_sha256="3" * 64,
        observed_resource_ledger_sha256="5" * 64,
        acceptance_sha256="4" * 64,
        realized_budget_match_verified=True,
    )


def test_sealed_ablation_requires_exact_common_12_seed_design() -> None:
    batch = _batch()
    assert batch.verify()
    with pytest.raises(ValueError, match="12 outputs"):
        SealedAblationBatch.freeze(
            _locks()[:-1],
            policy_sha256="1",
            prompt_sha256="2",
            budget_sha256="3",
            observed_resource_ledger_sha256="5",
            acceptance_sha256="4",
            realized_budget_match_verified=True,
        )
    duplicate = _locks()
    duplicate[-1] = replace(duplicate[-1], output_id=duplicate[0].output_id)
    with pytest.raises(ValueError, match="unique"):
        SealedAblationBatch.freeze(
            duplicate,
            policy_sha256="1",
            prompt_sha256="2",
            budget_sha256="3",
            observed_resource_ledger_sha256="5",
            acceptance_sha256="4",
            realized_budget_match_verified=True,
        )


def test_batch_cannot_lock_before_realized_budget_match() -> None:
    with pytest.raises(ValueError, match="realized budget"):
        SealedAblationBatch.freeze(
            _locks(),
            policy_sha256="1",
            prompt_sha256="2",
            budget_sha256="3",
            observed_resource_ledger_sha256="5",
            acceptance_sha256="4",
            realized_budget_match_verified=False,
        )


def test_private_evaluation_rejects_interim_scores_and_reports_paired_deltas() -> None:
    batch = _batch()
    scores = {
        item.output_id: {SystemArm.B: 0.90, SystemArm.B_PLUS: 0.91, SystemArm.C: 0.92}[item.arm]
        for item in batch.outputs
    }
    with pytest.raises(ValueError, match="once for every"):
        evaluate_sealed_private_batch(batch, dict(list(scores.items())[:-1]))
    invalid = dict(scores)
    invalid[next(iter(invalid))] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        evaluate_sealed_private_batch(batch, invalid)

    result = evaluate_sealed_private_batch(batch, scores)

    assert result.paired_seeds == 12
    assert result.private_auc_c_minus_b == pytest.approx(0.02)
    assert result.private_auc_c_minus_b_plus == pytest.approx(0.01)


def test_private_results_cannot_be_reused_for_ieee_tuning() -> None:
    assert_private_result_use_allowed(PrivateResultUse.RESEARCH_CONCLUSION)
    assert_private_result_use_allowed(PrivateResultUse.CONFIRMATORY_EXTERNAL)
    with pytest.raises(PermissionError, match="not a development signal"):
        assert_private_result_use_allowed(PrivateResultUse.ENSEMBLE_WEIGHT_TUNING)
