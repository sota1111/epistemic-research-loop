from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from epistemic_loop.controller.candidate_artifacts import CandidateArtifactValidator
from epistemic_loop.evaluation.primary_endpoint import (
    IEEE_CIS_TEST_ROWS,
    validate_ieee_cis_submission,
)

IEEE_CIS_SNAPSHOT_MEMBERS = ("manifest.json", "test.parquet", "train.parquet")
IEEE_CIS_CANDIDATE_SCHEMA_VERSION = "0.3.1"


def canonical_ieee_cis_dataset_hash(data_root: str | Path) -> str:
    """Hash the canonical immutable snapshot using one repository-wide convention."""

    root = Path(data_root)
    digest = hashlib.sha256()
    for name in IEEE_CIS_SNAPSHOT_MEMBERS:
        path = root / name
        if not path.is_file():
            raise FileNotFoundError(path)
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(str(path.stat().st_size).encode())
        digest.update(b"\0")
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


@dataclass(frozen=True)
class IEEECandidateMetadata:
    candidate_id: str
    source_agent: str
    git_commit: str
    dataset_hash: str
    environment_hash: str
    validation_protocol: str
    primary_score: float
    fold_scores: tuple[float, ...]
    seeds: tuple[int, ...]
    leakage_check_passed: bool
    reproducibility_passed: bool


class IEEECandidateSchemaSDK:
    """Produce the three metadata documents shared by isolated IEEE workers."""

    def documents(
        self,
        metadata: IEEECandidateMetadata,
        *,
        features: Sequence[str],
    ) -> dict[str, dict[str, Any]]:
        if len(metadata.fold_scores) < 3:
            raise ValueError("IEEE candidate metadata requires at least three forward folds")
        if len(metadata.seeds) < 1 or len(set(metadata.seeds)) != len(metadata.seeds):
            raise ValueError("candidate seeds must be non-empty and unique")
        if not features or len(features) != len(set(features)):
            raise ValueError("feature manifest must be non-empty and unique")
        mean = sum(metadata.fold_scores) / len(metadata.fold_scores)
        score_std = math.sqrt(sum((item - mean) ** 2 for item in metadata.fold_scores) / len(metadata.fold_scores))
        common = {
            "candidate_id": metadata.candidate_id,
            "dataset_hash": metadata.dataset_hash,
            "environment_hash": metadata.environment_hash,
            "schema_version": IEEE_CIS_CANDIDATE_SCHEMA_VERSION,
        }
        return {
            "candidate.yaml": {
                **common,
                "source_agent": metadata.source_agent,
                "git_commit": metadata.git_commit,
                "validation": {
                    "protocol": metadata.validation_protocol,
                    "primary_score": metadata.primary_score,
                    "fold_scores": list(metadata.fold_scores),
                    "score_std": score_std,
                },
                "leakage_check": {"passed": metadata.leakage_check_passed},
                "reproducibility": {
                    "passed": metadata.reproducibility_passed,
                    "seeds": list(metadata.seeds),
                },
            },
            "run_manifest.yaml": {
                **common,
                "seeds": list(metadata.seeds),
                "validation_protocol": metadata.validation_protocol,
            },
            "feature_manifest.yaml": {
                "schema_version": IEEE_CIS_CANDIDATE_SCHEMA_VERSION,
                "features": list(features),
                "fold_local_fit_required": True,
            },
        }


@dataclass(frozen=True)
class IEEEArtifactPreflightResult:
    valid: bool
    contract_valid: bool
    dataset_hash_matches: bool
    submission_row_count: int
    test_prediction_row_count: int
    oof_row_count: int
    oof_honesty_passed: bool
    errors: tuple[str, ...]


class IEEEArtifactPreflight:
    """Fail fast on row coverage and honest-OOF invariants before archive promotion."""

    def __init__(self, *, expected_test_rows: int = IEEE_CIS_TEST_ROWS):
        self.expected_test_rows = expected_test_rows
        self.contract = CandidateArtifactValidator()

    def validate(
        self,
        artifact_root: str | Path,
        *,
        expected_dataset_hash: str,
    ) -> IEEEArtifactPreflightResult:
        root = Path(artifact_root)
        errors: list[str] = []
        contract = self.contract.validate(root)
        if not contract.valid:
            errors.extend(contract.missing)
            errors.extend(contract.invalid)

        candidate = _yaml_mapping(root / "candidate.yaml")
        run_manifest = _yaml_mapping(root / "run_manifest.yaml")
        hashes = {str(value.get("dataset_hash", "")) for value in (candidate, run_manifest)}
        dataset_hash_matches = hashes == {expected_dataset_hash}
        if not dataset_hash_matches:
            errors.append("candidate and run manifest must use the canonical dataset hash")

        submission = validate_ieee_cis_submission(root / "submission.csv", expected_rows=self.expected_test_rows)
        errors.extend(submission.errors)
        test_rows = _parquet_row_count(root / "test_predictions.parquet")
        if test_rows != self.expected_test_rows:
            errors.append(f"test prediction row count is {test_rows}; expected {self.expected_test_rows}")
        oof_rows, oof_honesty, oof_errors = _validate_oof_honesty(
            root / "oof_predictions.parquet", root / "fold_assignment.parquet"
        )
        errors.extend(oof_errors)
        return IEEEArtifactPreflightResult(
            valid=not errors,
            contract_valid=contract.valid,
            dataset_hash_matches=dataset_hash_matches,
            submission_row_count=submission.row_count,
            test_prediction_row_count=test_rows,
            oof_row_count=oof_rows,
            oof_honesty_passed=oof_honesty,
            errors=tuple(dict.fromkeys(errors)),
        )


def _yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    import yaml

    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _parquet_row_count(path: Path) -> int:
    if not path.is_file():
        return 0
    from pyarrow import parquet as pq  # type: ignore[import-untyped]

    return int(pq.read_metadata(path).num_rows)


def _validate_oof_honesty(oof_path: Path, fold_path: Path) -> tuple[int, bool, tuple[str, ...]]:
    if not oof_path.is_file() or not fold_path.is_file():
        return 0, False, ("OOF prediction or fold assignment parquet is missing",)
    from pyarrow import parquet as pq

    required_oof = {"TransactionID", "prediction", "fold"}
    required_fold = {"TransactionID", "fold"}
    oof_schema = set(pq.read_schema(oof_path).names)
    fold_schema = set(pq.read_schema(fold_path).names)
    errors: list[str] = []
    if not required_oof <= oof_schema:
        errors.append(f"OOF schema is missing {sorted(required_oof - oof_schema)}")
    if not required_fold <= fold_schema:
        errors.append(f"fold schema is missing {sorted(required_fold - fold_schema)}")
    if errors:
        return _parquet_row_count(oof_path), False, tuple(errors)
    oof = pq.read_table(oof_path, columns=sorted(required_oof)).to_pydict()
    folds = pq.read_table(fold_path, columns=sorted(required_fold)).to_pydict()
    identifiers = [str(value) for value in oof["TransactionID"]]
    if len(identifiers) != len(set(identifiers)):
        errors.append("OOF TransactionID values must be unique")
    fold_by_id: dict[str, int] = {}
    for identifier, fold in zip(folds["TransactionID"], folds["fold"], strict=True):
        key = str(identifier)
        if key in fold_by_id:
            errors.append("fold assignment TransactionID values must be unique")
            break
        fold_by_id[key] = int(fold)
    for identifier, fold, prediction in zip(identifiers, oof["fold"], oof["prediction"], strict=True):
        value = float(prediction)
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            errors.append("OOF predictions must be finite probabilities")
            break
        if int(fold) < 0 or fold_by_id.get(identifier) != int(fold):
            errors.append("every OOF row must match a non-negative held-out fold assignment")
            break
    return len(identifiers), not errors, tuple(errors)


@dataclass(frozen=True)
class ColdReplayReliabilityGate:
    first_attempt_valid_artifact_rate: float
    resource_failure_rate: float
    final_test_row_count: int
    oof_honesty_passed: bool

    @property
    def passed(self) -> bool:
        return (
            self.first_attempt_valid_artifact_rate >= 0.95
            and self.resource_failure_rate <= 0.05
            and self.final_test_row_count == IEEE_CIS_TEST_ROWS
            and self.oof_honesty_passed
        )
