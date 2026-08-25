from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from epistemic_loop.domain.models import OOFRecord


@dataclass(frozen=True)
class OOFAnalysis:
    candidate_ids: tuple[str, ...]
    residual_correlations: dict[str, float]
    prediction_disagreements: dict[str, float]
    covariance_effective_rank: float


def _pearson(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("correlation needs non-empty sequences of equal length")
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    centered_left = [value - left_mean for value in left]
    centered_right = [value - right_mean for value in right]
    numerator = sum(a * b for a, b in zip(centered_left, centered_right, strict=True))
    denominator = math.sqrt(
        sum(value * value for value in centered_left) * sum(value * value for value in centered_right)
    )
    return 0.0 if denominator == 0 else numerator / denominator


def pairwise_residual_correlation(left: Sequence[OOFRecord], right: Sequence[OOFRecord]) -> float:
    paired = _pair(left, right)
    return _pearson([_residual(a) for a, _ in paired], [_residual(b) for _, b in paired])


def prediction_disagreement(left: Sequence[OOFRecord], right: Sequence[OOFRecord], *, threshold: float = 0.5) -> float:
    paired = _pair(left, right)
    return sum((a.oof_prediction >= threshold) != (b.oof_prediction >= threshold) for a, b in paired) / len(paired)


def effective_rank(residual_matrix: Sequence[Sequence[float]]) -> float:
    """Entropy effective rank of the candidate residual covariance matrix."""

    matrix = [list(map(float, row)) for row in residual_matrix]
    if not matrix:
        return 0.0
    width = len(matrix[0])
    if width < 2 or any(len(row) != width for row in matrix):
        raise ValueError("residual matrix rows must have an equal width of at least two")
    centered = []
    for row in matrix:
        average = sum(row) / width
        centered.append([value - average for value in row])
    covariance = [
        [sum(a * b for a, b in zip(left, right, strict=True)) / (width - 1) for right in centered] for left in centered
    ]
    eigenvalues = [max(0.0, value) for value in _symmetric_eigenvalues(covariance)]
    total = sum(eigenvalues)
    if total <= 1e-15:
        return 0.0
    probabilities = [value / total for value in eigenvalues if value > 1e-15]
    return math.exp(-sum(value * math.log(value) for value in probabilities))


def marginal_ensemble_gain(existing: Sequence[Sequence[OOFRecord]], candidate: Sequence[OOFRecord]) -> float:
    """Reduction in MSE when a candidate joins an equal-weight OOF blend."""

    if not existing:
        return 0.0
    candidate_map = _row_map(candidate)
    existing_maps = [_row_map(rows) for rows in existing]
    keys = set(candidate_map)
    for mapping in existing_maps:
        keys &= set(mapping)
    if not keys:
        raise ValueError("OOF candidates have no common rows")
    ordered = sorted(keys)
    before = after = 0.0
    for key in ordered:
        base_rows = [mapping[key] for mapping in existing_maps]
        targets = {row.target for row in [*base_rows, candidate_map[key]]}
        if len(targets) != 1:
            raise ValueError(f"target mismatch for OOF row {key}")
        target = targets.pop()
        base_prediction = sum(row.oof_prediction for row in base_rows) / len(base_rows)
        next_prediction = (sum(row.oof_prediction for row in base_rows) + candidate_map[key].oof_prediction) / (
            len(base_rows) + 1
        )
        before += (target - base_prediction) ** 2
        after += (target - next_prediction) ** 2
    return (before - after) / len(ordered)


def analyze(records: Iterable[OOFRecord]) -> OOFAnalysis:
    grouped: dict[str, list[OOFRecord]] = defaultdict(list)
    for record in records:
        grouped[record.candidate_id].append(record)
    identifiers = sorted(grouped)
    residuals: dict[str, float] = {}
    disagreements: dict[str, float] = {}
    for left_index, left in enumerate(identifiers):
        for right in identifiers[left_index + 1 :]:
            key = f"{left}::{right}"
            residuals[key] = pairwise_residual_correlation(grouped[left], grouped[right])
            disagreements[key] = prediction_disagreement(grouped[left], grouped[right])
    aligned = _aligned_residual_matrix([grouped[identifier] for identifier in identifiers])
    return OOFAnalysis(
        candidate_ids=tuple(identifiers),
        residual_correlations=residuals,
        prediction_disagreements=disagreements,
        covariance_effective_rank=effective_rank(aligned) if aligned else 0.0,
    )


def _row_map(rows: Sequence[OOFRecord]) -> dict[tuple[str, str], OOFRecord]:
    mapping = {(item.validation_world, item.row_id): item for item in rows}
    if len(mapping) != len(rows):
        raise ValueError("duplicate OOF row identity")
    return mapping


def _pair(left: Sequence[OOFRecord], right: Sequence[OOFRecord]) -> list[tuple[OOFRecord, OOFRecord]]:
    left_map = _row_map(left)
    right_map = _row_map(right)
    if set(left_map) != set(right_map):
        raise ValueError("OOF candidates must contain exactly the same validation rows")
    paired = [(left_map[key], right_map[key]) for key in sorted(left_map)]
    for first, second in paired:
        if first.target != second.target or first.fold_id != second.fold_id:
            raise ValueError(f"target or fold mismatch for OOF row {first.row_id}")
    return paired


def _aligned_residual_matrix(groups: Sequence[Sequence[OOFRecord]]) -> list[list[float]]:
    if not groups:
        return []
    reference = _row_map(groups[0])
    keys = sorted(reference)
    result = []
    for group in groups:
        mapping = _row_map(group)
        if set(mapping) != set(reference):
            raise ValueError("OOF candidates must contain exactly the same validation rows")
        result.append([_residual(mapping[key]) for key in keys])
    return result


def _residual(record: OOFRecord) -> float:
    if record.residual is None:  # Defensive for callers bypassing Pydantic validation.
        raise ValueError("OOF residual is missing")
    return record.residual


def _symmetric_eigenvalues(matrix: Sequence[Sequence[float]]) -> list[float]:
    """Jacobi eigensolver for the small candidate covariance matrices we store."""

    values = [list(row) for row in matrix]
    size = len(values)
    if any(len(row) != size for row in values):
        raise ValueError("eigenvalue input must be square")
    if size <= 1:
        return [values[0][0]] if size else []
    for _ in range(50 * size * size):
        p, q = max(
            ((i, j) for i in range(size) for j in range(i + 1, size)),
            key=lambda pair: abs(values[pair[0]][pair[1]]),
        )
        if abs(values[p][q]) < 1e-12:
            break
        phi = 0.5 * math.atan2(2 * values[p][q], values[q][q] - values[p][p])
        cosine, sine = math.cos(phi), math.sin(phi)
        app, aqq, apq = values[p][p], values[q][q], values[p][q]
        values[p][p] = cosine * cosine * app - 2 * sine * cosine * apq + sine * sine * aqq
        values[q][q] = sine * sine * app + 2 * sine * cosine * apq + cosine * cosine * aqq
        values[p][q] = values[q][p] = 0.0
        for index in range(size):
            if index in {p, q}:
                continue
            aip, aiq = values[index][p], values[index][q]
            values[index][p] = values[p][index] = cosine * aip - sine * aiq
            values[index][q] = values[q][index] = sine * aip + cosine * aiq
    return [values[index][index] for index in range(size)]
