from __future__ import annotations

import json
from pathlib import Path

import yaml

from epistemic_loop.controller.candidate_artifacts import V034CandidateArtifactValidator


def _write_candidate(root: Path, *, fold_hash: str = "fold-hash") -> None:
    (root / "model_artifact").mkdir()
    (root / "model_artifact/model.bin").write_bytes(b"model")
    candidate = {
        "candidate_id": "candidate-1",
        "source_agent": "agent-1",
        "git_commit": "abc",
        "dataset_hash": "dataset-hash",
        "environment_hash": "environment-hash",
        "fold_plan_hash": fold_hash,
        "validation": {"strict_forward": True},
        "oof_honesty": {"passed": True},
        "leakage_check": {"passed": True},
        "reproducibility": {"passed": True},
    }
    manifest = {
        "candidate_id": "candidate-1",
        "dataset_hash": "dataset-hash",
        "environment_hash": "environment-hash",
        "fold_plan_hash": fold_hash,
        "row_counts": {"test_predictions": 2, "submission": 2},
    }
    (root / "candidate.yaml").write_text(yaml.safe_dump(candidate), encoding="utf-8")
    (root / "run_manifest.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    (root / "feature_manifest.yaml").write_text(yaml.safe_dump({"features": ["x"]}), encoding="utf-8")
    for name in ("fold_assignment.parquet", "oof_predictions.parquet", "test_predictions.parquet"):
        (root / name).write_bytes(b"parquet-placeholder")
    (root / "metrics.json").write_text(json.dumps({"auc": 0.9}), encoding="utf-8")
    (root / "source_code_ref.json").write_text(
        json.dumps({"git_commit": "abc", "source_sha256": "source"}), encoding="utf-8"
    )
    (root / "environment_lock.json").write_text(
        json.dumps({"environment_hash": "environment-hash", "python": "3.11"}), encoding="utf-8"
    )
    (root / "submission.csv").write_text("TransactionID,isFraud\n1,0.1\n2,0.2\n", encoding="utf-8")


def test_v034_candidate_contract_checks_common_fold_and_submission_rows(tmp_path: Path) -> None:
    _write_candidate(tmp_path)
    validator = V034CandidateArtifactValidator()
    result = validator.validate(
        tmp_path,
        expected_dataset_hash="dataset-hash",
        expected_fold_plan_hash="fold-hash",
        expected_test_rows=2,
    )
    assert result.valid

    bad = validator.validate(
        tmp_path,
        expected_dataset_hash="dataset-hash",
        expected_fold_plan_hash="different",
        expected_test_rows=2,
    )
    assert not bad.valid
    assert any("fold_plan_hash" in item for item in bad.invalid)
