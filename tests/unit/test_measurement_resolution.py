"""The gate from `docs/v050_course_correction.md` §5 item 2.

The condition that has to be shown is one sentence: **a comparison whose interval spans zero
returns no ranking.** Everything else here supports that -- that the gate is not vacuous (a real
difference still separates), that it is not bypassable (`total_order` raises rather than degrading
to the mean), and that the planned half-width matches the `32/sqrt(n)` law the campaign measured.
"""

from __future__ import annotations

import math
import random
import statistics

import pytest

from epistemic_loop.measurement.resolution import (
    NEDO_SCALE_CONSTANT,
    ResolutionGateError,
    compare_pair,
    gated_ranking,
    paired_bootstrap_interval,
    paired_differences,
    required_task_count,
    resolution_half_width,
    scale_constant_from_spread,
)

#: Per-task spread of the *difference* implied by the measured law: 32 = 1.96 * spread.
CAMPAIGN_SPREAD = 16.33


def _standard_pattern(count: int) -> list[float]:
    """A deterministic stratified standard-normal sample: mean 0, population sd exactly 1.

    Deterministic on purpose. A test of a noise gate that draws its own noise passes or fails on
    the seed, which is the failure mode this whole module exists to stop.
    """
    normal = statistics.NormalDist()
    values = [normal.inv_cdf((index + 0.5) / count) for index in range(count)]
    scale = statistics.pstdev(values)
    return [value / scale for value in values]


def _scores(count: int, *, offset: float, spread: float, rotation: int = 0) -> dict[str, float]:
    """One candidate over ``count`` shared tasks: task difficulty, an offset, and per-task noise."""
    pattern = _standard_pattern(count)
    rotated = pattern[rotation:] + pattern[:rotation]
    return {f"t{index:04d}": 20.0 + 3.0 * index + offset + spread * rotated[index] for index in range(count)}


def _noisy_pair(
    count: int, *, separation: float, spread: float, rotation: int = 5
) -> tuple[dict[str, float], dict[str, float]]:
    """Two candidates whose paired differences have mean ``separation`` and spread ``spread``."""
    half = spread / math.sqrt(2)
    left = _scores(count, offset=separation, spread=half, rotation=0)
    right = _scores(count, offset=0.0, spread=half, rotation=rotation)
    return left, right


def test_difference_inside_the_noise_returns_no_ranking() -> None:
    """12 tasks and a 2-point difference: exactly the situation that reversed four conclusions in
    `docs/v050_lessons.md` §1.1. At 12 tasks the law resolves 9.2 points. The gate must refuse."""
    left, right = _noisy_pair(12, separation=2.0, spread=CAMPAIGN_SPREAD)

    verdict = compare_pair("P1", "P3", left, right)

    assert verdict.separated is False
    assert verdict.better is None
    low, high = verdict.interval
    assert low <= 0 <= high

    ranking = gated_ranking({"P1": left, "P3": right})
    assert ranking.resolved is False
    assert ranking.tiers == (("P1", "P3"),)
    assert ranking.undecided_pairs == (("P1", "P3"),)
    with pytest.raises(ResolutionGateError, match="no total order"):
        ranking.total_order()


def test_a_difference_the_task_count_can_see_is_still_ranked() -> None:
    """The gate must not be a blanket refusal: the 10.5-point evolution-vs-search difference was
    real and separable, and a comparator that hid it would be useless."""
    left, right = _noisy_pair(48, separation=10.5, spread=CAMPAIGN_SPREAD)

    verdict = compare_pair("evolution", "search", left, right)

    assert verdict.separated is True
    assert verdict.better == "evolution"
    assert verdict.interval[0] > 0
    assert gated_ranking({"evolution": left, "search": right}).total_order() == ("evolution", "search")


def test_more_tasks_can_resolve_what_fewer_cannot() -> None:
    """Same underlying difference, more tasks: the refusal is about the measurement, not the pair."""
    small_left, small_right = _noisy_pair(12, separation=3.0, spread=CAMPAIGN_SPREAD)
    large_left, large_right = _noisy_pair(600, separation=3.0, spread=CAMPAIGN_SPREAD)

    assert compare_pair("a", "b", small_left, small_right, resamples=2000).separated is False
    assert compare_pair("a", "b", large_left, large_right, resamples=2000).separated is True


def test_ties_group_into_one_tier_and_a_separated_candidate_opens_the_next() -> None:
    half = CAMPAIGN_SPREAD / math.sqrt(2)
    near_a = _scores(16, offset=0.4, spread=half, rotation=0)
    near_b = _scores(16, offset=0.0, spread=half, rotation=5)
    far = _scores(16, offset=-40.0, spread=half, rotation=9)

    ranking = gated_ranking({"a": near_a, "b": near_b, "c": far})

    assert ranking.tiers[0] == ("a", "b")
    assert ranking.tiers[1] == ("c",)
    assert ranking.leaders() == ("a", "b")
    assert ranking.resolved is False


def test_minimised_metrics_rank_the_other_way_round() -> None:
    left = {f"t{i}": 1.0 + 0.001 * i for i in range(40)}
    right = {f"t{i}": 5.0 + 0.001 * i for i in range(40)}

    assert compare_pair("low", "high", left, right, metric_direction="minimize").better == "low"
    assert compare_pair("low", "high", left, right, metric_direction="maximize").better == "high"


def test_a_single_shared_task_never_separates() -> None:
    verdict = compare_pair("a", "b", {"t0": 90.0}, {"t0": 10.0})

    assert verdict.separated is False
    assert "at least" in verdict.reason
    assert math.isinf(verdict.measured_half_width)


def test_identical_scores_do_not_manufacture_a_win_when_a_spread_floor_is_given() -> None:
    """Early rounds where every task scores the same collapse the sample spread to zero and, with
    it, the interval. `docs/v050_lessons.md` §1.7: floor the spread instead."""
    left = {f"t{i}": 50.5 for i in range(16)}
    right = {f"t{i}": 50.0 for i in range(16)}

    assert compare_pair("a", "b", left, right).separated is True
    assert compare_pair("a", "b", left, right, minimum_spread=8.0).separated is False


def test_paired_differences_use_only_shared_tasks() -> None:
    tasks, differences = paired_differences({"t0": 1.0, "t1": 3.0, "t2": 9.0}, {"t1": 1.0, "t2": 4.0, "t9": 0.0})

    assert tasks == ("t1", "t2")
    assert differences == (2.0, 5.0)


def test_the_planned_half_width_follows_the_measured_law() -> None:
    """`half-width = 32 / sqrt(tasks)`, and the task counts it implies for the differences the
    campaign cared about (`docs/v050_lessons.md` §1.1)."""
    assert resolution_half_width(128) == pytest.approx(2.83, abs=0.01)
    assert required_task_count(20.0) == 3
    assert required_task_count(10.0) == 11
    assert required_task_count(5.0) == 41
    assert required_task_count(2.0) == 256

    # The constant is scale-specific and re-fits from an observed per-task spread.
    assert scale_constant_from_spread(NEDO_SCALE_CONSTANT / 1.959963984540054) == pytest.approx(NEDO_SCALE_CONSTANT)


def test_bootstrap_interval_brackets_the_mean_and_is_seed_stable() -> None:
    rng = random.Random(1)
    differences = [rng.gauss(2.0, 3.0) for _ in range(64)]

    first = paired_bootstrap_interval(differences, resamples=2000, seed=17)
    second = paired_bootstrap_interval(differences, resamples=2000, seed=17)
    mean = sum(differences) / len(differences)

    assert first == second
    assert first[0] <= mean <= first[1]


def test_empty_and_degenerate_inputs_are_refused() -> None:
    with pytest.raises(ValueError):
        paired_bootstrap_interval([])
    with pytest.raises(ValueError):
        resolution_half_width(0)
    with pytest.raises(ValueError):
        required_task_count(0)
    assert gated_ranking({}).tiers == ()
