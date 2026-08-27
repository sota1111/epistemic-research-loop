from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path

import yaml

from epistemic_loop.domain.enums import TerminalStatus
from epistemic_loop.domain.models import CandidateArtifactValidation
from epistemic_loop.evaluation.primary_endpoint import validate_ieee_cis_submission

CANDIDATE_ARTIFACT_CONTRACT = (
    "candidate.yaml",
    "run_manifest.yaml",
    "feature_manifest.yaml",
    "fold_assignment.parquet",
    "oof_predictions.parquet",
    "test_predictions.parquet",
    "metrics.json",
    "model_artifact",
    "submission.csv",
    "source_code_ref",
    "environment_lock",
)

V034_CANDIDATE_ARTIFACT_CONTRACT = (
    "candidate.yaml",
    "run_manifest.yaml",
    "feature_manifest.yaml",
    "fold_assignment.parquet",
    "oof_predictions.parquet",
    "test_predictions.parquet",
    "metrics.json",
    "model_artifact",
    "submission.csv",
    "source_code_ref.json",
    "environment_lock.json",
)


def candidate_required_outputs() -> list[str]:
    return list(CANDIDATE_ARTIFACT_CONTRACT)


class CandidateArtifactValidator:
    """Validate promotion artifacts without importing a solver dataframe stack."""

    def validate(self, root: str | Path) -> CandidateArtifactValidation:
        directory = Path(root)
        missing = [name for name in CANDIDATE_ARTIFACT_CONTRACT if not (directory / name).exists()]
        invalid: list[str] = []
        model_dir = directory / "model_artifact"
        if model_dir.exists() and (not model_dir.is_dir() or not any(model_dir.iterdir())):
            invalid.append("model_artifact must be a non-empty directory")
        for name in (
            "fold_assignment.parquet",
            "oof_predictions.parquet",
            "test_predictions.parquet",
            "submission.csv",
            "source_code_ref",
            "environment_lock",
        ):
            path = directory / name
            if path.exists() and (not path.is_file() or path.stat().st_size == 0):
                invalid.append(f"{name} must be a non-empty file")

        candidate = self._mapping(directory / "candidate.yaml", invalid)
        run_manifest = self._mapping(directory / "run_manifest.yaml", invalid)
        feature_manifest = self._mapping(directory / "feature_manifest.yaml", invalid)
        metrics = self._json_mapping(directory / "metrics.json", invalid)
        if candidate:
            required = {"candidate_id", "source_agent", "git_commit", "dataset_hash", "environment_hash"}
            absent = sorted(required - set(candidate))
            if absent:
                invalid.append(f"candidate.yaml missing keys: {absent}")
            validation = candidate.get("validation")
            if not isinstance(validation, dict) or not {
                "protocol",
                "primary_score",
                "fold_scores",
                "score_std",
            } <= set(validation):
                invalid.append("candidate.yaml validation section is incomplete")
            leakage = candidate.get("leakage_check")
            if not isinstance(leakage, dict) or leakage.get("passed") is not True:
                invalid.append("candidate leakage_check.passed must be true")
            reproducibility = candidate.get("reproducibility")
            if not isinstance(reproducibility, dict) or reproducibility.get("passed") is not True:
                invalid.append("candidate reproducibility.passed must be true")
        if run_manifest and not {"candidate_id", "dataset_hash", "environment_hash"} <= set(run_manifest):
            invalid.append("run_manifest.yaml is incomplete")
        if feature_manifest and not isinstance(feature_manifest.get("features"), list):
            invalid.append("feature_manifest.yaml requires a features list")
        if metrics and not any(isinstance(value, (int, float)) for value in metrics.values()):
            invalid.append("metrics.json contains no numeric metric")

        if missing or invalid:
            leakage_invalid = any("leakage" in item for item in invalid)
            return CandidateArtifactValidation(
                valid=False,
                terminal_status=(
                    TerminalStatus.INVALID_LEAKAGE if leakage_invalid else TerminalStatus.INVALID_ARTIFACT
                ),
                missing=missing,
                invalid=invalid,
            )
        return CandidateArtifactValidation(valid=True, terminal_status=TerminalStatus.COMPLETED)

    @staticmethod
    def _mapping(path: Path, invalid: list[str]) -> dict[str, object]:
        if not path.is_file():
            return {}
        try:
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            invalid.append(f"{path.name} cannot be parsed: {exc}")
            return {}
        if not isinstance(value, dict):
            invalid.append(f"{path.name} must contain an object")
            return {}
        return value

    @staticmethod
    def _json_mapping(path: Path, invalid: list[str]) -> dict[str, object]:
        if not path.is_file():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            invalid.append(f"{path.name} cannot be parsed: {exc}")
            return {}
        if not isinstance(value, dict):
            invalid.append(f"{path.name} must contain an object")
            return {}
        return value


class V034CandidateArtifactValidator(CandidateArtifactValidator):
    """Validate the stricter outcome-only common-crossfit candidate contract."""

    def validate(
        self,
        root: str | Path,
        *,
        expected_dataset_hash: str | None = None,
        expected_fold_plan_hash: str | None = None,
        expected_test_rows: int = 506_691,
    ) -> CandidateArtifactValidation:
        directory = Path(root)
        missing = [name for name in V034_CANDIDATE_ARTIFACT_CONTRACT if not (directory / name).exists()]
        invalid: list[str] = []
        model_dir = directory / "model_artifact"
        if model_dir.exists() and (not model_dir.is_dir() or not any(model_dir.iterdir())):
            invalid.append("model_artifact must be a non-empty directory")
        for name in V034_CANDIDATE_ARTIFACT_CONTRACT:
            path = directory / name
            if name == "model_artifact" or not path.exists():
                continue
            if not path.is_file() or path.stat().st_size == 0:
                invalid.append(f"{name} must be a non-empty file")

        candidate = self._mapping(directory / "candidate.yaml", invalid)
        manifest = self._mapping(directory / "run_manifest.yaml", invalid)
        features = self._mapping(directory / "feature_manifest.yaml", invalid)
        metrics = self._json_mapping(directory / "metrics.json", invalid)
        source_ref = self._json_mapping(directory / "source_code_ref.json", invalid)
        environment = self._json_mapping(directory / "environment_lock.json", invalid)

        if candidate:
            required = {
                "candidate_id",
                "source_agent",
                "git_commit",
                "dataset_hash",
                "environment_hash",
                "fold_plan_hash",
            }
            absent = sorted(required - set(candidate))
            if absent:
                invalid.append(f"candidate.yaml missing keys: {absent}")
            validation = candidate.get("validation")
            if not isinstance(validation, dict) or validation.get("strict_forward") is not True:
                invalid.append("candidate validation.strict_forward must be true")
            honesty = candidate.get("oof_honesty")
            if not isinstance(honesty, dict) or honesty.get("passed") is not True:
                invalid.append("candidate oof_honesty.passed must be true")
            leakage = candidate.get("leakage_check")
            if not isinstance(leakage, dict) or leakage.get("passed") is not True:
                invalid.append("candidate leakage_check.passed must be true")
            reproducibility = candidate.get("reproducibility")
            if not isinstance(reproducibility, dict) or reproducibility.get("passed") is not True:
                invalid.append("candidate reproducibility.passed must be true")
            if expected_dataset_hash is not None and candidate.get("dataset_hash") != expected_dataset_hash:
                invalid.append("candidate dataset_hash does not match the immutable snapshot")
            if expected_fold_plan_hash is not None and candidate.get("fold_plan_hash") != expected_fold_plan_hash:
                invalid.append("candidate fold_plan_hash does not match the common plan")

        if manifest:
            required_manifest = {"candidate_id", "dataset_hash", "environment_hash", "fold_plan_hash", "row_counts"}
            if not required_manifest <= set(manifest):
                invalid.append("run_manifest.yaml is incomplete")
            row_counts = manifest.get("row_counts")
            if not isinstance(row_counts, dict) or row_counts.get("test_predictions") != expected_test_rows:
                invalid.append("run manifest test prediction row count is invalid")
            if not isinstance(row_counts, dict) or row_counts.get("submission") != expected_test_rows:
                invalid.append("run manifest submission row count is invalid")
        if features and not isinstance(features.get("features"), list):
            invalid.append("feature_manifest.yaml requires a features list")
        if metrics and not any(isinstance(value, (int, float)) for value in metrics.values()):
            invalid.append("metrics.json contains no numeric metric")
        if source_ref and not {"git_commit", "source_sha256"} <= set(source_ref):
            invalid.append("source_code_ref.json is incomplete")
        if environment and not {"environment_hash", "python"} <= set(environment):
            invalid.append("environment_lock.json is incomplete")

        submission_path = directory / "submission.csv"
        if submission_path.is_file():
            submission = validate_ieee_cis_submission(submission_path, expected_rows=expected_test_rows)
            invalid.extend(f"submission: {error}" for error in submission.errors)

        if missing or invalid:
            leakage_invalid = any("leakage" in item for item in invalid)
            return CandidateArtifactValidation(
                valid=False,
                terminal_status=(
                    TerminalStatus.INVALID_LEAKAGE if leakage_invalid else TerminalStatus.INVALID_ARTIFACT
                ),
                missing=missing,
                invalid=invalid,
            )
        return CandidateArtifactValidation(valid=True, terminal_status=TerminalStatus.COMPLETED)


def hash_snapshot(paths: Iterable[str | Path]) -> str:
    """Content hash a stable collection without mutating the dataset/environment."""

    digest = hashlib.sha256()
    resolved = sorted((Path(item).resolve() for item in paths), key=str)
    for path in resolved:
        if not path.exists():
            raise FileNotFoundError(path)
        members = [path] if path.is_file() else sorted(item for item in path.rglob("*") if item.is_file())
        for member in members:
            digest.update(str(member.relative_to(path.parent if path.is_file() else path)).encode())
            digest.update(b"\0")
            with member.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"
