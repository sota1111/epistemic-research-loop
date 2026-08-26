from __future__ import annotations

import csv
import hashlib
import json
import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

IEEE_CIS_TEST_ROWS = 506_691


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class SubmissionValidation:
    valid: bool
    row_count: int
    sha256: str
    errors: tuple[str, ...]
    minimum_prediction: float | None = None
    maximum_prediction: float | None = None


def validate_ieee_cis_submission(
    path: str | Path,
    *,
    expected_rows: int = IEEE_CIS_TEST_ROWS,
) -> SubmissionValidation:
    source = Path(path)
    errors: list[str] = []
    row_count = 0
    identifiers: set[str] = set()
    minimum: float | None = None
    maximum: float | None = None
    if not source.is_file():
        return SubmissionValidation(False, 0, "", (f"submission not found: {source}",))
    with source.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["TransactionID", "isFraud"]:
            errors.append("columns must be exactly TransactionID,isFraud")
        for row_number, row in enumerate(reader, start=2):
            row_count += 1
            identifier = (row.get("TransactionID") or "").strip()
            prediction_text = (row.get("isFraud") or "").strip()
            if not identifier:
                errors.append(f"row {row_number} has an empty TransactionID")
                continue
            if identifier in identifiers:
                errors.append(f"duplicate TransactionID: {identifier}")
            identifiers.add(identifier)
            try:
                prediction = float(prediction_text)
            except ValueError:
                errors.append(f"row {row_number} has a non-numeric prediction")
                continue
            if not math.isfinite(prediction) or not 0.0 <= prediction <= 1.0:
                errors.append(f"row {row_number} prediction is outside [0, 1]")
                continue
            minimum = prediction if minimum is None else min(minimum, prediction)
            maximum = prediction if maximum is None else max(maximum, prediction)
    if row_count != expected_rows:
        errors.append(f"row count is {row_count}; expected {expected_rows}")
    if len(identifiers) != row_count:
        errors.append("TransactionID values are not unique and complete")
    return SubmissionValidation(
        valid=not errors,
        row_count=row_count,
        sha256=sha256_file(source),
        errors=tuple(dict.fromkeys(errors)),
        minimum_prediction=minimum,
        maximum_prediction=maximum,
    )


@dataclass(frozen=True)
class FrozenSubmissionSpec:
    submission_id: str
    path: str
    expected_sha256: str
    purpose: str
    local_forward_auc: float
    local_protocol: str
    kaggle_description: str
    expected_rows: int = IEEE_CIS_TEST_ROWS

    def verify(self, repository_root: str | Path) -> SubmissionValidation:
        validation = validate_ieee_cis_submission(Path(repository_root) / self.path, expected_rows=self.expected_rows)
        errors = list(validation.errors)
        if validation.sha256 != self.expected_sha256:
            errors.append(f"sha256 changed for {self.submission_id}: {validation.sha256} != {self.expected_sha256}")
        return SubmissionValidation(
            valid=not errors,
            row_count=validation.row_count,
            sha256=validation.sha256,
            errors=tuple(errors),
            minimum_prediction=validation.minimum_prediction,
            maximum_prediction=validation.maximum_prediction,
        )


@dataclass(frozen=True)
class FrozenSubmissionBatch:
    competition: str
    submissions: tuple[FrozenSubmissionSpec, ...]
    frozen_at: str
    batch_sha256: str
    late_submission_endpoint_only: bool = True

    def verify(self, repository_root: str | Path) -> dict[str, SubmissionValidation]:
        return {item.submission_id: item.verify(repository_root) for item in self.submissions}

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_path(cls, path: str | Path) -> FrozenSubmissionBatch:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        specs = tuple(FrozenSubmissionSpec(**item) for item in value.pop("submissions"))
        batch = cls(submissions=specs, **value)
        expected = _batch_sha256(batch.competition, batch.submissions)
        if expected != batch.batch_sha256:
            raise ValueError("frozen batch manifest hash is invalid")
        return batch


def _batch_sha256(competition: str, submissions: Sequence[FrozenSubmissionSpec]) -> str:
    stable = {
        "competition": competition,
        "submissions": [asdict(item) for item in submissions],
        "late_submission_endpoint_only": True,
    }
    encoded = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def freeze_submission_batch(
    *,
    repository_root: str | Path,
    competition: str,
    submissions: Sequence[FrozenSubmissionSpec],
    output_path: str | Path,
    frozen_at: datetime | None = None,
) -> FrozenSubmissionBatch:
    if not submissions:
        raise ValueError("a frozen batch requires at least one submission")
    identifiers = [item.submission_id for item in submissions]
    descriptions = [item.kaggle_description for item in submissions]
    if len(identifiers) != len(set(identifiers)) or len(descriptions) != len(set(descriptions)):
        raise ValueError("submission identifiers and Kaggle descriptions must be unique")
    batch = FrozenSubmissionBatch(
        competition=competition,
        submissions=tuple(submissions),
        frozen_at=(frozen_at or datetime.now(UTC)).isoformat(),
        batch_sha256=_batch_sha256(competition, submissions),
    )
    validations = batch.verify(repository_root)
    invalid = {name: result.errors for name, result in validations.items() if not result.valid}
    if invalid:
        raise ValueError(f"cannot freeze an invalid submission batch: {invalid}")
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(batch.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return batch


def rank_values(values: Sequence[float], *, higher_is_better: bool = True) -> tuple[float, ...]:
    """Return deterministic average ranks, with rank one assigned to the best value."""

    direction = -1.0 if higher_is_better else 1.0
    ordered = sorted(enumerate(values), key=lambda item: (direction * item[1], item[0]))
    ranks = [0.0] * len(values)
    position = 0
    while position < len(ordered):
        end = position + 1
        while end < len(ordered) and ordered[end][1] == ordered[position][1]:
            end += 1
        average_rank = ((position + 1) + end) / 2.0
        for index, _ in ordered[position:end]:
            ranks[index] = average_rank
        position = end
    return tuple(ranks)


def spearman_rank_consistency(local_scores: Sequence[float], private_scores: Sequence[float]) -> float | None:
    if len(local_scores) != len(private_scores) or len(local_scores) < 2:
        return None
    left = rank_values(local_scores)
    right = rank_values(private_scores)
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right, strict=True))
    denominator = math.sqrt(sum((a - left_mean) ** 2 for a in left) * sum((b - right_mean) ** 2 for b in right))
    return numerator / denominator if denominator else None


def leaderboard_rank_equivalent(score: float, leaderboard_scores: Sequence[float]) -> float | None:
    """Map a post-hoc score to the average historical rank at the same score."""

    if not leaderboard_scores:
        return None
    better = sum(item > score for item in leaderboard_scores)
    equal = sum(item == score for item in leaderboard_scores)
    if equal:
        return ((better + 1) + (better + equal)) / 2.0
    return float(better + 1)
