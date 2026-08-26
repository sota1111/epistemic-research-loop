from __future__ import annotations

import math
import uuid
from collections.abc import Mapping, Sequence

from epistemic_loop.domain.enums import ValidationWorldStatus
from epistemic_loop.domain.models import (
    ValidationDiagnostics,
    ValidationWorld,
    ValidationWorldEvidence,
    ValidationWorldUpdate,
)

PROBABILITY_TOLERANCE = 1e-6


def _active(worlds: Sequence[ValidationWorld]) -> list[ValidationWorld]:
    return [item for item in worlds if item.status == ValidationWorldStatus.ACTIVE]


def validate_world_distribution(worlds: Sequence[ValidationWorld]) -> None:
    active = _active(worlds)
    if len(active) < 2:
        raise ValueError("at least two active validation worlds are required")
    identifiers = [item.id for item in active]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("validation world identifiers must be unique")
    run_ids = {item.run_id for item in worlds}
    if len(run_ids) != 1:
        raise ValueError("validation worlds must belong to one run")
    total = sum(item.posterior_probability for item in active)
    if abs(total - 1.0) > PROBABILITY_TOLERANCE:
        raise ValueError("active validation-world probabilities must sum to 1")


def update_worlds(
    worlds: Sequence[ValidationWorld], evidence: ValidationWorldEvidence
) -> tuple[list[ValidationWorld], ValidationWorldUpdate]:
    """Apply one preregistered likelihood update and return immutable new worlds."""

    validate_world_distribution(worlds)
    active = _active(worlds)
    if any(item.run_id != evidence.run_id for item in active):
        raise ValueError("validation evidence belongs to another run")
    active_ids = {item.id for item in active}
    supplied_ids = set(evidence.likelihood_by_world)
    if supplied_ids != active_ids:
        missing = sorted(active_ids - supplied_ids)
        extra = sorted(supplied_ids - active_ids)
        raise ValueError(f"world likelihoods must cover active worlds exactly (missing={missing}, extra={extra})")

    prior = {item.id: item.posterior_probability for item in active}
    # Reliability tempers weak or poorly replicated evidence. At reliability 0
    # the likelihood ratio tends to one; at 1 the registered likelihood is used.
    unnormalized = {
        identifier: probability * evidence.likelihood_by_world[identifier] ** evidence.reliability
        for identifier, probability in prior.items()
    }
    normalizer = sum(unnormalized.values())
    if normalizer <= 0:
        raise ValueError("validation evidence assigns zero probability to every active world")
    posterior = {identifier: value / normalizer for identifier, value in unnormalized.items()}
    updated = [
        item.model_copy(
            update={
                "posterior_probability": posterior[item.id],
                "evidence_ids": [*item.evidence_ids, evidence.id],
                "version": item.version + 1,
            }
        )
        if item.id in posterior
        else item
        for item in worlds
    ]
    update = ValidationWorldUpdate(
        id=f"VWU-{uuid.uuid4().hex[:12]}",
        run_id=evidence.run_id,
        evidence_id=evidence.id,
        prior=prior,
        posterior=posterior,
    )
    return updated, update


def posterior_entropy(worlds: Sequence[ValidationWorld], *, normalized: bool = False) -> float:
    active = _active(worlds)
    if not active:
        return 0.0
    values = [item.posterior_probability for item in active]
    total = sum(values)
    if total <= 0:
        return 0.0
    probabilities = [value / total for value in values]
    entropy = -sum(value * math.log2(value) for value in probabilities if value > 0)
    if normalized and len(probabilities) > 1:
        return entropy / math.log2(len(probabilities))
    return entropy


def validation_fidelity(
    diagnostics: ValidationDiagnostics,
    *,
    rank_weight: float = 0.35,
    pseudo_future_weight: float = 0.35,
    variance_weight: float = 0.15,
    leakage_weight: float = 0.15,
) -> float | None:
    """Combine available diagnostics without treating missing values as zero.

    Variance is mapped to a bounded stability score as 1/(1+variance). The
    supplied weights are renormalized over metrics that were actually observed.
    """

    components: list[tuple[float, float]] = []
    if diagnostics.model_rank_stability is not None:
        components.append((rank_weight, (diagnostics.model_rank_stability + 1) / 2))
    if diagnostics.pseudo_future_accuracy is not None:
        components.append((pseudo_future_weight, diagnostics.pseudo_future_accuracy))
    if diagnostics.score_variance is not None:
        components.append((variance_weight, 1 / (1 + diagnostics.score_variance)))
    if diagnostics.leakage_risk is not None:
        components.append((leakage_weight, 1 - diagnostics.leakage_risk))
    total_weight = sum(weight for weight, _ in components)
    if total_weight == 0:
        return None
    return sum(weight * value for weight, value in components) / total_weight


def expected_score(worlds: Sequence[ValidationWorld], scores: Mapping[str, float]) -> float:
    active = _active(worlds)
    active_ids = {item.id for item in active}
    if set(scores) != active_ids:
        raise ValueError("scores must cover every active validation world exactly")
    total = sum(item.posterior_probability for item in active)
    if total <= 0:
        raise ValueError("validation-world posterior has no probability mass")
    return sum(item.posterior_probability * scores[item.id] for item in active) / total


def spearman_rank_correlation(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    """Rank stability for the same candidate set, with average ranks for ties."""

    if set(left) != set(right) or len(left) < 2:
        raise ValueError("rank correlation needs the same two-or-more candidates in both worlds")
    identifiers = sorted(left)
    left_ranks = _average_ranks([left[item] for item in identifiers])
    right_ranks = _average_ranks([right[item] for item in identifiers])
    left_mean = sum(left_ranks) / len(left_ranks)
    right_mean = sum(right_ranks) / len(right_ranks)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left_ranks, right_ranks, strict=True))
    denominator = math.sqrt(
        sum((value - left_mean) ** 2 for value in left_ranks) * sum((value - right_mean) ** 2 for value in right_ranks)
    )
    return 0.0 if denominator == 0 else numerator / denominator


def rank_reversal_rate(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    if set(left) != set(right) or len(left) < 2:
        raise ValueError("rank reversal needs the same two-or-more candidates in both worlds")
    identifiers = sorted(left)
    reversals = comparable = 0
    for index, first in enumerate(identifiers):
        for second in identifiers[index + 1 :]:
            left_delta = left[first] - left[second]
            right_delta = right[first] - right[second]
            if left_delta == 0 or right_delta == 0:
                continue
            comparable += 1
            reversals += (left_delta > 0) != (right_delta > 0)
    return 0.0 if comparable == 0 else reversals / comparable


def _average_ranks(values: Sequence[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and ordered[end][1] == ordered[start][1]:
            end += 1
        average = (start + 1 + end) / 2
        for index in range(start, end):
            ranks[ordered[index][0]] = average
        start = end
    return ranks
