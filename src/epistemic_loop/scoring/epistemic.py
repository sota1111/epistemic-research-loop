from __future__ import annotations

import math
from collections.abc import Mapping

from epistemic_loop.domain.models import EpistemicAssessment, HypothesisOutcomeForecast


def epistemic_value_v1(assessment: EpistemicAssessment) -> float:
    return assessment.score


def binary_hypothesis_information_gain(prior: float, forecast: HypothesisOutcomeForecast) -> float:
    """Return I(H; Y) in bits for a preregistered categorical outcome model.

    Computing mutual information directly avoids rewarding a proposal merely because its author
    assigned itself a high uncertainty-reduction rubric. A value of one is the maximum for a binary
    hypothesis; uninformative equal likelihood vectors return zero.
    """
    if not 0 <= prior <= 1:
        raise ValueError("hypothesis prior must be between 0 and 1")
    information_nats = 0.0
    for outcome in forecast.outcomes:
        if_true = outcome.probability_if_true
        if_false = outcome.probability_if_false
        marginal = prior * if_true + (1 - prior) * if_false
        if marginal == 0:
            continue
        if prior and if_true:
            information_nats += prior * if_true * math.log(if_true / marginal)
        if prior < 1 and if_false:
            information_nats += (1 - prior) * if_false * math.log(if_false / marginal)
    # Floating-point cancellation can produce a tiny negative number for equal vectors.
    return max(0.0, information_nats / math.log(2))


def epistemic_value_v2(
    forecasts: list[HypothesisOutcomeForecast],
    beliefs: Mapping[str, float],
) -> float | None:
    """Mean belief-conditioned EIG, or None when a proposal still uses the v1 schema.

    Taking the mean prevents a proposer from inflating its score by copying the same forecast across
    many hypothesis identifiers. Dependence between genuinely different hypotheses is not modelled
    yet; portfolio-level information redundancy is the next implementation slice.
    """
    values = [
        binary_hypothesis_information_gain(beliefs[item.hypothesis_id], item)
        for item in forecasts
        if item.hypothesis_id in beliefs
    ]
    if not values:
        return None
    return sum(values) / len(values)
