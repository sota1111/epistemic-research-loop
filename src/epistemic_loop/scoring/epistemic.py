from __future__ import annotations

import math
import random
from collections.abc import Mapping
from typing import Literal

from epistemic_loop.domain.models import EpistemicAssessment, EVSIProxy, HypothesisOutcomeForecast


def epistemic_value_v1(assessment: EpistemicAssessment) -> float:
    return assessment.score


def evsi_proxy_value(proxy: EVSIProxy | None) -> float | None:
    return None if proxy is None else proxy.value


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


def monte_carlo_binary_information_gain(
    prior: float,
    forecast: HypothesisOutcomeForecast,
    *,
    samples: int = 4000,
    seed: int = 101,
) -> float:
    """Approximate EIG using the preregistered likelihood model and a local seeded RNG."""

    if not 0 <= prior <= 1:
        raise ValueError("hypothesis prior must be between 0 and 1")
    if samples < 1:
        raise ValueError("samples must be positive")
    if prior in {0.0, 1.0}:
        return 0.0
    generator = random.Random(seed)
    information = 0.0
    for _ in range(samples):
        hypothesis_true = generator.random() < prior
        likelihoods = [
            item.probability_if_true if hypothesis_true else item.probability_if_false for item in forecast.outcomes
        ]
        draw = generator.random()
        cumulative = 0.0
        selected = forecast.outcomes[-1]
        for outcome, probability in zip(forecast.outcomes, likelihoods, strict=True):
            cumulative += probability
            if draw <= cumulative:
                selected = outcome
                break
        marginal = prior * selected.probability_if_true + (1 - prior) * selected.probability_if_false
        posterior = prior * selected.probability_if_true / marginal if marginal else prior
        information += _bernoulli_kl_bits(posterior, prior)
    return information / samples


def _bernoulli_kl_bits(posterior: float, prior: float) -> float:
    value = 0.0
    if posterior:
        value += posterior * math.log(posterior / prior)
    if posterior < 1:
        value += (1 - posterior) * math.log((1 - posterior) / (1 - prior))
    return max(0.0, value / math.log(2))


def epistemic_value_v2(
    forecasts: list[HypothesisOutcomeForecast],
    beliefs: Mapping[str, float],
    *,
    method: Literal["exact", "monte_carlo"] = "exact",
    monte_carlo_samples: int = 4000,
    seed: int = 101,
) -> float | None:
    """Mean belief-conditioned EIG, or None when a proposal still uses the v1 schema.

    Taking the mean prevents a proposer from inflating its score by copying the same forecast across
    many hypothesis identifiers. Dependence between genuinely different hypotheses is not modelled
    yet; portfolio-level information redundancy is the next implementation slice.
    """
    values: list[float] = []
    for index, item in enumerate(forecasts):
        if item.hypothesis_id not in beliefs:
            continue
        if method == "monte_carlo":
            value = monte_carlo_binary_information_gain(
                beliefs[item.hypothesis_id],
                item,
                samples=monte_carlo_samples,
                seed=seed + index,
            )
        else:
            value = binary_hypothesis_information_gain(beliefs[item.hypothesis_id], item)
        values.append(value)
    if not values:
        return None
    return sum(values) / len(values)
