"""Per-cycle artifact contract for the outcome-only B/B+/C comparison."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from epistemic_loop.evaluation.v032 import SystemArm

BASE_CYCLE_ARTIFACTS = (
    "proposal.yaml",
    "decision_binding.yaml",
    "semantic_signature.yaml",
    "experiment_source",
    "local_metrics.json",
    "parent_predictions.parquet",
    "challenger_predictions.parquet",
    "decision_result.yaml",
    "artifact_validation.json",
)

PREDICTIVE_CYCLE_ARTIFACTS = (
    "expected_error_slice.yaml",
    "predicted_mechanism.yaml",
)

EPISTEMIC_CYCLE_ARTIFACTS = (
    "hypothesis.yaml",
    "alternatives.yaml",
    "falsification.yaml",
    "belief_update.yaml",
    "validation_debt.yaml",
)


@dataclass(frozen=True)
class CycleArtifactValidation:
    valid: bool
    missing: tuple[str, ...]
    invalid: tuple[str, ...]


class CycleArtifactContract:
    @staticmethod
    def required(arm: SystemArm) -> tuple[str, ...]:
        required = list(BASE_CYCLE_ARTIFACTS)
        if arm in {SystemArm.B_PLUS, SystemArm.C}:
            required.extend(PREDICTIVE_CYCLE_ARTIFACTS)
        if arm is SystemArm.C:
            required.extend(EPISTEMIC_CYCLE_ARTIFACTS)
        return tuple(required)

    def validate(self, root: str | Path, arm: SystemArm) -> CycleArtifactValidation:
        directory = Path(root)
        missing: list[str] = []
        invalid: list[str] = []
        for name in self.required(arm):
            path = directory / name
            if not path.exists():
                missing.append(name)
                continue
            if name == "experiment_source":
                if not path.is_dir() or not any(item.is_file() for item in path.rglob("*")):
                    invalid.append("experiment_source must be a non-empty directory")
            elif not path.is_file() or path.stat().st_size == 0:
                invalid.append(f"{name} must be a non-empty file")
        return CycleArtifactValidation(not missing and not invalid, tuple(missing), tuple(invalid))


V034_LOCKED_RUN_ARTIFACTS = (
    "run_manifest.json",
    "agent_reports",
    "cycle_decisions",
    "common_crossfit",
    "sealed_predictions",
    "locked_candidate_manifest.json",
    "locked_selection_reason.json",
    "final_retrain_lock.json",
    "locked_submission.csv",
    "locked_submission.sha256",
)


class V034LockedRunContract:
    """Validate one locked run before it can enter the 36-output batch."""

    def validate(self, root: str | Path) -> CycleArtifactValidation:
        directory = Path(root)
        missing = [name for name in V034_LOCKED_RUN_ARTIFACTS if not (directory / name).exists()]
        invalid: list[str] = []
        for name in ("agent_reports", "cycle_decisions", "common_crossfit", "sealed_predictions"):
            path = directory / name
            if path.exists() and (not path.is_dir() or not any(item.is_file() for item in path.rglob("*"))):
                invalid.append(f"{name} must be a non-empty directory")
        reports = directory / "agent_reports"
        if reports.is_dir() and len([item for item in reports.iterdir() if item.is_file()]) != 3:
            invalid.append("agent_reports must contain exactly three agent reports")
        decisions = directory / "cycle_decisions"
        if decisions.is_dir() and len([item for item in decisions.iterdir() if item.is_file()]) != 9:
            invalid.append("cycle_decisions must contain exactly nine decision locks")
        for name in V034_LOCKED_RUN_ARTIFACTS:
            path = directory / name
            if name in {"agent_reports", "cycle_decisions", "common_crossfit", "sealed_predictions"}:
                continue
            if path.exists() and (not path.is_file() or path.stat().st_size == 0):
                invalid.append(f"{name} must be a non-empty file")
        submission = directory / "locked_submission.csv"
        checksum = directory / "locked_submission.sha256"
        if submission.is_file() and checksum.is_file():
            checksum_parts = checksum.read_text(encoding="utf-8").strip().split()
            expected = checksum_parts[0] if checksum_parts else ""
            actual = _file_sha256(submission)
            if expected != actual:
                invalid.append("locked submission checksum mismatch")
        return CycleArtifactValidation(not missing and not invalid, tuple(missing), tuple(invalid))


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
