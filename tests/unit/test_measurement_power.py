"""Arm sizes are decided before the experiment, not after it fails to separate (§4).

The course-correction document says an arm of five needs six points. That number had no arithmetic
behind it, and it turns out to be optimistic: the design it describes sees 9.5 points at
conventional power, and 6.9 even at power 0.5. The point of this module is that the number is
computed and can be argued with.
"""

from __future__ import annotations

import pytest

from epistemic_loop.measurement.power import (
    arm_size_for,
    measurement_spread,
    plan_arm,
    student_t_quantile,
    total_spread,
)

# The campaign's own figures: 128-task ranking resolves +/-2.8, individuals spread 4 to 5 points.
HALF_WIDTH = 2.8
SPREAD = 4.5


def test_t_quantiles_match_published_tables() -> None:
    """Checked against a table, not against itself. A continued fraction that is subtly wrong
    returns plausible numbers, and every arm size here would inherit the error."""
    assert student_t_quantile(0.975, 1) == pytest.approx(12.7062, abs=1e-4)
    assert student_t_quantile(0.975, 8) == pytest.approx(2.3060, abs=1e-4)
    assert student_t_quantile(0.95, 10) == pytest.approx(1.8125, abs=1e-4)
    assert student_t_quantile(0.80, 20) == pytest.approx(0.8600, abs=1e-4)
    assert student_t_quantile(0.975, 30) == pytest.approx(2.0423, abs=1e-4)
    # Converges on the normal quantile as the degrees of freedom grow.
    assert student_t_quantile(0.975, 100_000) == pytest.approx(1.9600, abs=1e-3)


def test_both_sources_of_spread_are_counted() -> None:
    """Measurement error does not disappear because the individuals also differ."""
    assert measurement_spread(HALF_WIDTH) == pytest.approx(1.4286, abs=1e-4)
    assert total_spread(SPREAD, HALF_WIDTH) == pytest.approx(4.7213, abs=1e-4)
    assert total_spread(SPREAD, 0.0) == SPREAD


def test_five_per_arm_cannot_see_six_points() -> None:
    """§4 of `docs/v050_course_correction.md` says six. At five per arm it is 9.5."""
    plan = plan_arm(5, individual_spread=SPREAD, measurement_half_width=HALF_WIDTH)

    assert plan.detectable_difference == pytest.approx(9.54, abs=0.02)
    assert plan.can_see(10.5) is True  # evolution against search, the one difference that separated
    assert plan.can_see(6.0) is False


def test_even_at_coin_flip_power_five_per_arm_needs_nearly_seven() -> None:
    """The document's six points is not recoverable even by dropping power to 0.5."""
    plan = plan_arm(5, individual_spread=SPREAD, measurement_half_width=HALF_WIDTH, power=0.5)

    assert plan.detectable_difference == pytest.approx(6.89, abs=0.02)


def test_required_arm_size_grows_as_the_difference_shrinks() -> None:
    assert arm_size_for(10.5, individual_spread=SPREAD, measurement_half_width=HALF_WIDTH) == 5
    assert arm_size_for(6.0, individual_spread=SPREAD, measurement_half_width=HALF_WIDTH) == 11
    assert arm_size_for(3.0, individual_spread=SPREAD, measurement_half_width=HALF_WIDTH) == 40


def test_more_tasks_per_individual_help_less_than_more_individuals() -> None:
    """Perfect scoring of five individuals still cannot see six points: the between-individual
    spread is the larger term and no amount of scoring reduces it."""
    perfect = plan_arm(5, individual_spread=SPREAD, measurement_half_width=0.0)

    assert perfect.detectable_difference > 6.0
    assert (
        perfect.detectable_difference
        < plan_arm(5, individual_spread=SPREAD, measurement_half_width=HALF_WIDTH).detectable_difference
    )


def test_degenerate_designs_are_refused() -> None:
    with pytest.raises(ValueError, match="at least two"):
        plan_arm(1, individual_spread=SPREAD, measurement_half_width=HALF_WIDTH)
    with pytest.raises(ValueError):
        plan_arm(5, individual_spread=SPREAD, measurement_half_width=HALF_WIDTH, power=1.0)
    with pytest.raises(ValueError):
        arm_size_for(0.0, individual_spread=SPREAD, measurement_half_width=HALF_WIDTH)
    with pytest.raises(ValueError):
        measurement_spread(-1.0)
