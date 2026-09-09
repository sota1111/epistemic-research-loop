"""How many individuals an arm needs before a difference between arms can be seen.

`docs/v050_course_correction.md` §4: "each arm of five separates nothing under six points -- decide
the number of individuals first." That instruction has no arithmetic behind it in the repository,
and the experiment it governs (item 12, C against B) is the one the whole programme rests on.

Two sources of spread stack here and both have to be in the calculation:

* **measurement** -- one individual's score is itself an estimate, with the half-width
  `measurement/resolution.py` computes. A 128-task ranking resolves ±2.8 points, so an
  individual's score carries a standard error of about 1.4.
* **between individuals** -- two individuals built the same way still differ, by 4 to 5 points in
  the campaign that produced these numbers. This is usually the larger of the two, and no amount of
  extra scoring reduces it.

The arms are compared through their *means*, so what matters is the total per-individual spread
divided by the square root of the arm size -- and the quantiles are Student's t, not normal,
because an arm of five has eight degrees of freedom. Using the normal quantile there understates
the required arm by about a fifth, in the direction of running an experiment that cannot answer its
question.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from epistemic_loop.measurement.resolution import DEFAULT_CONFIDENCE, z_for_confidence

#: Conventional power. Stated rather than assumed: at 0.5 an experiment is a coin flip on a real
#: effect of exactly the size it was designed for.
DEFAULT_POWER = 0.80
DEFAULT_ALPHA = 0.05

#: The largest arm this will search to. Beyond it the answer is "not with this design".
MAXIMUM_ARM_SIZE = 10_000


def measurement_spread(half_width: float, *, confidence: float = DEFAULT_CONFIDENCE) -> float:
    """Standard error of one individual's score, from the half-width its ranking resolves."""
    if half_width < 0:
        raise ValueError("half_width must be non-negative")
    return half_width / z_for_confidence(confidence)


def total_spread(individual_spread: float, measurement_half_width: float) -> float:
    """Between-individual spread and measurement error, added in quadrature."""
    if individual_spread < 0:
        raise ValueError("individual_spread must be non-negative")
    return math.hypot(individual_spread, measurement_spread(measurement_half_width))


@dataclass(frozen=True)
class ArmPlan:
    """What an experiment of this shape can and cannot see."""

    arm_size: int
    detectable_difference: float
    power: float
    alpha: float
    individual_spread: float
    measurement_half_width: float
    standard_error: float

    def can_see(self, difference: float) -> bool:
        return difference >= self.detectable_difference

    def summary(self) -> str:
        return (
            f"{self.arm_size} per arm sees {self.detectable_difference:.2f} points "
            f"at power {self.power:.2f}, alpha {self.alpha:.2f} "
            f"(between-individual {self.individual_spread:.2f}, "
            f"measurement half-width {self.measurement_half_width:.2f})"
        )


def plan_arm(
    arm_size: int,
    *,
    individual_spread: float,
    measurement_half_width: float,
    power: float = DEFAULT_POWER,
    alpha: float = DEFAULT_ALPHA,
) -> ArmPlan:
    """The smallest difference between arm means this design can detect."""
    if arm_size < 2:
        raise ValueError("an arm needs at least two individuals")
    if not 0 < power < 1 or not 0 < alpha < 1:
        raise ValueError("power and alpha must be in (0, 1)")
    spread = total_spread(individual_spread, measurement_half_width)
    standard_error = spread * math.sqrt(2 / arm_size)
    degrees = 2 * arm_size - 2
    difference = (student_t_quantile(1 - alpha / 2, degrees) + student_t_quantile(power, degrees)) * standard_error
    return ArmPlan(
        arm_size=arm_size,
        detectable_difference=difference,
        power=power,
        alpha=alpha,
        individual_spread=individual_spread,
        measurement_half_width=measurement_half_width,
        standard_error=standard_error,
    )


def arm_size_for(
    difference: float,
    *,
    individual_spread: float,
    measurement_half_width: float,
    power: float = DEFAULT_POWER,
    alpha: float = DEFAULT_ALPHA,
) -> int:
    """Individuals per arm needed before ``difference`` is detectable. Decide this first."""
    if difference <= 0:
        raise ValueError("difference must be positive")
    size = 2
    while size <= MAXIMUM_ARM_SIZE:
        if plan_arm(
            size,
            individual_spread=individual_spread,
            measurement_half_width=measurement_half_width,
            power=power,
            alpha=alpha,
        ).can_see(difference):
            return size
        size += 1
    raise ValueError(
        f"a difference of {difference} is not reachable with fewer than {MAXIMUM_ARM_SIZE} individuals per arm; "
        f"reduce the between-individual spread or accept a larger difference"
    )


def student_t_quantile(probability: float, degrees_of_freedom: int) -> float:
    """Inverse Student-t CDF by bisection on the CDF. Accurate to ~1e-9 over the range used here."""
    if not 0 < probability < 1:
        raise ValueError("probability must be in (0, 1)")
    if degrees_of_freedom < 1:
        raise ValueError("degrees_of_freedom must be at least 1")
    if abs(probability - 0.5) < 1e-15:
        return 0.0
    low, high = -1e4, 1e4
    for _ in range(200):
        middle = (low + high) / 2
        if _student_t_cdf(middle, degrees_of_freedom) < probability:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def _student_t_cdf(value: float, degrees_of_freedom: int) -> float:
    tail = 0.5 * _regularized_incomplete_beta(
        degrees_of_freedom / (degrees_of_freedom + value * value),
        degrees_of_freedom / 2,
        0.5,
    )
    return 1 - tail if value > 0 else tail


def _regularized_incomplete_beta(x: float, a: float, b: float) -> float:
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return front * _beta_continued_fraction(x, a, b) / a
    return 1 - front * _beta_continued_fraction(1 - x, b, a) / b


def _beta_continued_fraction(x: float, a: float, b: float, iterations: int = 300) -> float:
    """Lentz's algorithm for the continued fraction of the incomplete beta function.

    The first odd term is the initial value of ``d``; the loop therefore starts at the even term of
    m = 1. Applying the m = 0 odd term again inside the loop silently returns numbers that look
    plausible and are not -- which is why `student_t_quantile` is checked against published table
    values rather than against itself.
    """
    tiny = 1e-30
    c = 1.0
    d = 1 - (a + b) * x / (a + 1)
    d = tiny if abs(d) < tiny else d
    d = 1 / d
    result = d
    for m in range(1, iterations + 1):
        even = m * (b - m) * x / ((a + 2 * m - 1) * (a + 2 * m))
        odd = -(a + m) * (a + b + m) * x / ((a + 2 * m) * (a + 2 * m + 1))
        for numerator in (even, odd):
            d = 1 + numerator * d
            d = tiny if abs(d) < tiny else d
            d = 1 / d
            c = 1 + numerator / c
            c = tiny if abs(c) < tiny else c
            delta = c * d
            result *= delta
        if abs(delta - 1) < 1e-14:
            break
    return result
