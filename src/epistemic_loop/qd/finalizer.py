from __future__ import annotations

from collections.abc import Sequence

from epistemic_loop.domain.models import QDCandidate


def final_candidate_utility(
    candidate: QDCandidate,
    *,
    robustness_weight: float = 0.15,
    diversity_weight: float = 0.15,
    variance_weight: float = 1.0,
    cost_weight: float = 0.1,
    leakage_weight: float = 1.0,
) -> float:
    return (
        candidate.expected_hidden_score
        + robustness_weight * candidate.robustness
        + diversity_weight * candidate.error_diversity
        - variance_weight * candidate.score_variance
        - cost_weight * candidate.normalized_cost
        - leakage_weight * candidate.leakage_risk
    )


def select_final_candidate(candidates: Sequence[QDCandidate]) -> QDCandidate:
    if not candidates:
        raise ValueError("final selection requires at least one QD candidate")
    return max(candidates, key=lambda item: (final_candidate_utility(item), item.id))
