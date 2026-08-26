from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path

import pytest

from epistemic_loop.controller.stagnation import (
    ExplorationProgressSnapshot,
    ExplorationStagnationDetector,
    PredictiveCollapseDetector,
    PredictiveCollapseMetrics,
    PredictiveDiversityDebt,
    PredictiveDiversityDebtRegistry,
    PredictiveDiversityDebtStatus,
)
from epistemic_loop.evaluation.acceptance import AcceptanceStatus, V031AcceptanceReport
from epistemic_loop.evaluation.primary_endpoint import (
    FrozenSubmissionBatch,
    FrozenSubmissionSpec,
    freeze_submission_batch,
    leaderboard_rank_equivalent,
    sha256_file,
    spearman_rank_consistency,
    validate_ieee_cis_submission,
)
from epistemic_loop.plugins.ieee_cis import IEEERunAcceptance
from epistemic_loop.plugins.ieee_cis_artifacts import (
    ColdReplayReliabilityGate,
    IEEECandidateMetadata,
    IEEECandidateSchemaSDK,
    canonical_ieee_cis_dataset_hash,
)


def _submission(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["TransactionID", "isFraud"])
        writer.writerows([(1, 0.1), (2, 0.8)])


def test_frozen_endpoint_batch_rejects_post_freeze_artifact_change(tmp_path: Path) -> None:
    source = tmp_path / "submission.csv"
    _submission(source)
    validation = validate_ieee_cis_submission(source, expected_rows=2)
    assert validation.valid
    spec = FrozenSubmissionSpec(
        submission_id="baseline",
        path="submission.csv",
        expected_sha256=sha256_file(source),
        purpose="baseline",
        local_forward_auc=0.7,
        local_protocol="common_forward",
        kaggle_description="frozen baseline",
        expected_rows=2,
    )
    manifest = tmp_path / "frozen.json"
    batch = freeze_submission_batch(
        repository_root=tmp_path,
        competition="ieee-fraud-detection",
        submissions=[spec],
        output_path=manifest,
        frozen_at=datetime(2026, 8, 26, tzinfo=UTC),
    )
    assert FrozenSubmissionBatch.from_path(manifest).batch_sha256 == batch.batch_sha256
    source.write_text("TransactionID,isFraud\n1,0.9\n2,0.8\n", encoding="utf-8")
    assert batch.verify(tmp_path)["baseline"].valid is False


def test_local_private_rank_consistency() -> None:
    assert spearman_rank_consistency([0.1, 0.2, 0.3], [0.7, 0.8, 0.9]) == pytest.approx(1.0)
    assert spearman_rank_consistency([0.1, 0.2, 0.3], [0.9, 0.8, 0.7]) == pytest.approx(-1.0)
    assert leaderboard_rank_equivalent(0.85, [0.9, 0.85, 0.85, 0.8]) == 2.5


def test_stagnation_is_distinct_from_semantic_collapse() -> None:
    detector = ExplorationStagnationDetector()
    decisions = [
        detector.assess(ExplorationProgressSnapshot(1, 9, 0, 0.87, 1)),
        detector.assess(ExplorationProgressSnapshot(2, 9, 0, 0.87, 1)),
        detector.assess(ExplorationProgressSnapshot(3, 9, 0, 0.87, 1)),
    ]
    assert decisions[1].stagnated is False
    assert decisions[2].stagnated is True
    assert set(decisions[2].active_conditions) == {
        "qd_occupancy_not_increased",
        "no_new_validated_structure",
        "accepted_primary_metric_not_improved",
        "validation_debt_not_reduced",
    }


def test_predictive_collapse_opens_generic_debt_and_debt_has_evidence_gate(tmp_path: Path) -> None:
    decision = PredictiveCollapseDetector().assess(
        PredictiveCollapseMetrics(
            candidate_count=9,
            residual_effective_rank=1.107745,
            mean_residual_correlation=0.975,
            nested_ensemble_auc_gain=-0.003,
        )
    )
    assert decision.collapsed
    assert decision.notification is not None
    assert "CatBoost" not in decision.notification

    debt = PredictiveDiversityDebt(
        debt_id="PDD-01",
        candidate_id="CAND-NEW",
        preregistered_data_slice="late new-client rows",
        proposed_error_mechanism="history is unavailable for new clients",
        archive_residual_correlation_floor=0.97,
        quality_floor=0.85,
    )
    assert (
        debt.assess_candidate(
            candidate_quality=0.84,
            minimum_residual_correlation=0.90,
            nested_marginal_auc_gain=0.01,
        ).status
        == PredictiveDiversityDebtStatus.OPEN
    )
    assert (
        debt.assess_candidate(
            candidate_quality=0.86,
            minimum_residual_correlation=0.96,
            nested_marginal_auc_gain=0.0,
        ).status
        == PredictiveDiversityDebtStatus.RESOLVED
    )
    registry = PredictiveDiversityDebtRegistry(tmp_path / "predictive-debts")
    registry.open(debt)
    resolved = registry.assess(
        debt.debt_id,
        candidate_quality=0.86,
        minimum_residual_correlation=0.96,
        nested_marginal_auc_gain=0.0,
    )
    assert resolved.status == PredictiveDiversityDebtStatus.RESOLVED
    assert registry.get(debt.debt_id) == resolved


def test_four_layer_acceptance_preserves_unmeasured_primary_endpoint() -> None:
    ieee = IEEERunAcceptance(
        validated_behavioral_client_proxies=0,
        forward_horizons=3,
        fold_safe_uid_candidates=0,
        known_new_client_slice=False,
        model_families=frozenset({"lightgbm"}),
        oof_candidates=9,
        ensemble_candidates=1,
        locked_submissions=1,
    )
    report = V031AcceptanceReport.assess(
        control_plane_checks={"generic_agents": True, "artifact_contract": True},
        structure_checks={"dynamic_fork": True, "terminal_debt": False},
        ieee_cis=ieee,
        locked_private_auc=None,
        matched_baseline_private_auc=None,
        baseline_is_matched=False,
        multi_seed_passed=False,
        multiple_competitions_passed=False,
        validated_high_leverage_structures=0,
    )
    assert report.control_plane.status == AcceptanceStatus.PASS
    assert report.dynamic_structure_mechanism.status == AcceptanceStatus.PARTIAL_PASS
    assert report.ieee_cis_capability.status == AcceptanceStatus.FAIL
    assert report.primary_endpoint.status == AcceptanceStatus.UNMEASURED
    assert report.generic_structure_success is False


def test_measured_primary_endpoint_fails_until_all_primary_gates_pass() -> None:
    ieee = IEEERunAcceptance(0, 3, 0, False, frozenset({"lightgbm"}), 3, 1, 1)
    report = V031AcceptanceReport.assess(
        control_plane_checks={"artifact_contract": True},
        structure_checks={"terminal_debt": True},
        ieee_cis=ieee,
        locked_private_auc=0.893519,
        matched_baseline_private_auc=0.905709,
        baseline_is_matched=False,
        multi_seed_passed=True,
        multiple_competitions_passed=False,
        validated_high_leverage_structures=0,
    )
    assert report.primary_endpoint.status == AcceptanceStatus.FAIL


def test_canonical_hash_has_stable_filename_size_content_framing(tmp_path: Path) -> None:
    for name, value in {
        "manifest.json": "{}",
        "test.parquet": "test",
        "train.parquet": "train",
    }.items():
        (tmp_path / name).write_text(value, encoding="utf-8")
    first = canonical_ieee_cis_dataset_hash(tmp_path)
    assert first.startswith("sha256:")
    assert first == canonical_ieee_cis_dataset_hash(tmp_path)
    (tmp_path / "train.parquet").write_text("changed", encoding="utf-8")
    assert canonical_ieee_cis_dataset_hash(tmp_path) != first


def test_clean_replay_reliability_uses_first_attempt_and_exact_test_coverage() -> None:
    passed = ColdReplayReliabilityGate(0.95, 0.05, 506_691, True)
    assert passed.passed
    assert ColdReplayReliabilityGate(0.949, 0.0, 506_691, True).passed is False
    assert ColdReplayReliabilityGate(1.0, 0.0, 80_000, True).passed is False


def test_ieee_candidate_schema_sdk_emits_shared_forward_contract() -> None:
    documents = IEEECandidateSchemaSDK().documents(
        IEEECandidateMetadata(
            candidate_id="CAND-01",
            source_agent="island-01",
            git_commit="abc",
            dataset_hash="sha256:data",
            environment_hash="sha256:env",
            validation_protocol="common_forward_gap",
            primary_score=0.9,
            fold_scores=(0.89, 0.90, 0.91),
            seeds=(17, 42, 20260826),
            leakage_check_passed=True,
            reproducibility_passed=True,
        ),
        features=("amount", "time"),
    )
    assert set(documents) == {"candidate.yaml", "run_manifest.yaml", "feature_manifest.yaml"}
    assert documents["candidate.yaml"]["validation"]["score_std"] > 0
    assert documents["feature_manifest.yaml"]["fold_local_fit_required"] is True
