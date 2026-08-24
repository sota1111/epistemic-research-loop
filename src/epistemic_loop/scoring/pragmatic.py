from __future__ import annotations

from epistemic_loop.domain.models import ScoreEstimate


def robust_score_gain(
    estimate: ScoreEstimate,
    *,
    fold_penalty: float = 1.0,
    seed_penalty: float = 1.0,
    group_penalty: float = 1.0,
    uncertainty_penalty: float = 0.5,
) -> float:
    return (
        estimate.mean_gain
        - fold_penalty * estimate.fold_std
        - seed_penalty * estimate.seed_std
        - group_penalty * estimate.worst_group_gap
        - uncertainty_penalty * estimate.uncertainty
    )
