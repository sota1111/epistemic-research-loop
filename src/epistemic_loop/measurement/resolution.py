"""Resolution: how small a difference a comparison can actually see.

The rule this module exists to enforce is the first item of the measurement discipline in
`docs/v050_course_correction.md` §3: **estimate the half-width before comparing, and return no
ranking for a comparison whose interval spans zero.**

The cost of not having it is recorded in `docs/v050_lessons.md` §1.1. Twelve tasks with a per-task
spread of 2.58 points were used to rank individuals two or three points apart. Re-measured on 128
tasks, four conclusions reversed -- the parent-beating rate was 5/6 rather than 1/4, the supposed
best individual of a cell was its worst, and a "consistently better" ordering was backwards. Every
one of those judgements was made inside the noise, and nothing about the output looked wrong.

Two half-widths appear here and they answer different questions:

* the **planned** half-width, ``scale_constant / sqrt(task_count)``, is what a comparison on this
  many tasks can be expected to resolve *before* any of it is run. It is what decides how many
  tasks to buy.
* the **measured** half-width comes from a paired bootstrap over the per-task differences and is
  what the gate actually rules on.

The planned form is a law fitted on one competition (32 points, agreeing within 0.23 points for
n=8..128); the constant belongs to that scoring scale, not to the universe, so it is a parameter
here and :func:`scale_constant_from_spread` re-fits it from an observed per-task spread.
"""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from epistemic_loop.scoring.normalization import higher_is_better

#: The constant fitted on the NEDO loading competition: half-width [points] = 32 / sqrt(tasks).
#: It is scale-specific. Re-fit it with :func:`scale_constant_from_spread` for any other scoring
#: system before quoting a required task count from it.
NEDO_SCALE_CONSTANT = 32.0

#: Two-sided 95% is the interval every comparison in this project is written against.
DEFAULT_CONFIDENCE = 0.95

#: Below this a paired bootstrap cannot say anything: one task has no spread to resample.
MINIMUM_COMPARABLE_TASKS = 2

_Z95 = 1.959963984540054


class ResolutionGateError(RuntimeError):
    """Raised when a total order is demanded of a comparison that cannot resolve one."""


def resolution_half_width(task_count: int, *, scale_constant: float = NEDO_SCALE_CONSTANT) -> float:
    """The difference a paired comparison over ``task_count`` tasks is expected to resolve."""
    if task_count <= 0:
        raise ValueError("task_count must be positive")
    return scale_constant / math.sqrt(task_count)


def required_task_count(target_difference: float, *, scale_constant: float = NEDO_SCALE_CONSTANT) -> int:
    """Tasks needed before a difference of ``target_difference`` is separable from zero.

    This is the number to write down *before* designing a round. Its growth is the whole point:
    halving the difference you want to see quadruples the tasks you have to score.
    """
    if target_difference <= 0:
        raise ValueError("target_difference must be positive")
    return math.ceil((scale_constant / target_difference) ** 2)


def scale_constant_from_spread(per_task_spread: float, *, confidence: float = DEFAULT_CONFIDENCE) -> float:
    """Re-fit the ``c / sqrt(n)`` constant from an observed spread of per-task differences.

    ``half_width = z * spread / sqrt(n)``, so the constant is ``z * spread``. Use this the first
    time a new scoring system is scored on more than a handful of tasks, and never carry another
    competition's constant across.
    """
    if per_task_spread < 0:
        raise ValueError("per_task_spread must be non-negative")
    return z_for_confidence(confidence) * per_task_spread


def paired_differences(
    left: Mapping[str, float],
    right: Mapping[str, float],
    *,
    metric_direction: str = "maximize",
) -> tuple[tuple[str, ...], tuple[float, ...]]:
    """Per-task differences over the tasks both candidates were scored on, higher-is-better.

    Pairing is the reason a comparison over a few dozen tasks says anything at all: task difficulty
    is far larger than the difference between two candidates, and it cancels only when both are
    scored on the *same* task. Tasks scored for one candidate and not the other are dropped, which
    is why the task list is returned rather than assumed.
    """
    shared = sorted(set(left) & set(right))
    differences = tuple(
        higher_is_better(left[task], metric_direction) - higher_is_better(right[task], metric_direction)
        for task in shared
    )
    return tuple(shared), differences


def paired_bootstrap_interval(
    differences: Sequence[float],
    *,
    resamples: int = 10_000,
    confidence: float = DEFAULT_CONFIDENCE,
    seed: int = 0,
    minimum_spread: float | None = None,
) -> tuple[float, float]:
    """Percentile interval for the mean paired difference, resampling tasks with replacement.

    ``minimum_spread`` is a floor on the per-task standard deviation, and it is not cosmetic. When
    early tasks happen to score identically the sample spread collapses to zero, the interval
    collapses with it, and the comparison reports a decisive win from what is actually no evidence
    (`docs/v050_lessons.md` §1.7). Where a floor is known for the scoring system, pass it: the
    interval is then widened to the normal-approximation width implied by that floor.
    """
    count = len(differences)
    if count == 0:
        raise ValueError("differences must not be empty")
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(resamples):
        total = 0.0
        for _ in range(count):
            total += differences[rng.randrange(count)]
        means.append(total / count)
    means.sort()
    tail = (1 - confidence) / 2
    low = _percentile(means, tail)
    high = _percentile(means, 1 - tail)
    if minimum_spread is not None:
        centre = sum(differences) / count
        floor = z_for_confidence(confidence) * minimum_spread / math.sqrt(count)
        low = min(low, centre - floor)
        high = max(high, centre + floor)
    return low, high


@dataclass(frozen=True)
class ComparisonVerdict:
    """What one paired comparison is entitled to claim.

    ``separated`` is the gate. When it is false there is no better candidate, not a weakly better
    one: :attr:`better` is ``None`` and callers must not fall back to the mean.
    """

    left: str
    right: str
    task_count: int
    mean_difference: float
    interval: tuple[float, float]
    measured_half_width: float
    planned_half_width: float
    separated: bool
    reason: str

    @property
    def better(self) -> str | None:
        if not self.separated:
            return None
        return self.left if self.mean_difference > 0 else self.right

    def summary(self) -> str:
        low, high = self.interval
        verdict = f"{self.better} is better" if self.separated else "indistinguishable"
        return (
            f"{self.left} vs {self.right}: mean {self.mean_difference:+.3f}, "
            f"95% [{low:+.3f}, {high:+.3f}] over {self.task_count} tasks -> {verdict} ({self.reason})"
        )


def compare_pair(  # noqa: PLR0913
    left: str,
    right: str,
    left_scores: Mapping[str, float],
    right_scores: Mapping[str, float],
    *,
    metric_direction: str = "maximize",
    scale_constant: float = NEDO_SCALE_CONSTANT,
    resamples: int = 10_000,
    confidence: float = DEFAULT_CONFIDENCE,
    seed: int = 0,
    minimum_spread: float | None = None,
) -> ComparisonVerdict:
    """Compare two candidates on their common tasks and say whether the difference is visible."""
    tasks, differences = paired_differences(left_scores, right_scores, metric_direction=metric_direction)
    count = len(tasks)
    if count < MINIMUM_COMPARABLE_TASKS:
        return ComparisonVerdict(
            left=left,
            right=right,
            task_count=count,
            mean_difference=sum(differences) / count if count else 0.0,
            interval=(-math.inf, math.inf),
            measured_half_width=math.inf,
            planned_half_width=math.inf,
            separated=False,
            reason=f"only {count} shared task(s); a paired interval needs at least {MINIMUM_COMPARABLE_TASKS}",
        )
    mean = sum(differences) / count
    low, high = paired_bootstrap_interval(
        differences,
        resamples=resamples,
        confidence=confidence,
        seed=seed,
        minimum_spread=minimum_spread,
    )
    spans_zero = low <= 0 <= high
    planned = resolution_half_width(count, scale_constant=scale_constant)
    return ComparisonVerdict(
        left=left,
        right=right,
        task_count=count,
        mean_difference=mean,
        interval=(low, high),
        measured_half_width=(high - low) / 2,
        planned_half_width=planned,
        separated=not spans_zero,
        reason=(
            "interval spans zero; this many tasks cannot see this difference"
            if spans_zero
            else "interval excludes zero"
        ),
    )


@dataclass(frozen=True)
class GatedRanking:
    """A ranking that stops where the measurement stops.

    Candidates inside one tier were not separated from each other, so the tier is unordered by
    construction. :meth:`total_order` exists only to make the refusal loud: code that needs a
    strict order has to ask for one and be told no, rather than reading position 0 of a list that
    quietly encodes noise.
    """

    tiers: tuple[tuple[str, ...], ...]
    comparisons: tuple[ComparisonVerdict, ...]
    task_count: int
    planned_half_width: float

    @property
    def resolved(self) -> bool:
        return all(len(tier) == 1 for tier in self.tiers)

    @property
    def undecided_pairs(self) -> tuple[tuple[str, str], ...]:
        return tuple((item.left, item.right) for item in self.comparisons if not item.separated)

    def leaders(self) -> tuple[str, ...]:
        """The top tier. One name only when the top really was separated from the runner-up."""
        return self.tiers[0] if self.tiers else ()

    def total_order(self) -> tuple[str, ...]:
        if not self.resolved:
            unordered = "; ".join("/".join(tier) for tier in self.tiers if len(tier) > 1)
            raise ResolutionGateError(
                f"no total order at {self.task_count} tasks: {unordered} are within the resolution "
                f"(planned half-width {self.planned_half_width:.3f}). "
                f"Score more tasks or report the tiers."
            )
        return tuple(tier[0] for tier in self.tiers)


def gated_ranking(  # noqa: PLR0913
    scores: Mapping[str, Mapping[str, float]],
    *,
    metric_direction: str = "maximize",
    scale_constant: float = NEDO_SCALE_CONSTANT,
    resamples: int = 10_000,
    confidence: float = DEFAULT_CONFIDENCE,
    seed: int = 0,
    minimum_spread: float | None = None,
) -> GatedRanking:
    """Rank candidates by paired comparison, refusing to order what cannot be ordered.

    Candidates are visited best-mean-first and a new tier is opened only when the next candidate is
    separated from *every* member of the current tier. A tier therefore never asserts an ordering
    that the measurement does not support, and the common failure -- reading a leaderboard whose
    top few entries are one bootstrap apart -- becomes a tier of several names instead of a winner.
    """
    ordered = sorted(
        scores,
        key=lambda candidate: -_mean(scores[candidate].values(), metric_direction),
    )
    tiers: list[list[str]] = []
    comparisons: list[ComparisonVerdict] = []
    for candidate in ordered:
        if not tiers:
            tiers.append([candidate])
            continue
        current = tiers[-1]
        verdicts = [
            compare_pair(
                member,
                candidate,
                scores[member],
                scores[candidate],
                metric_direction=metric_direction,
                scale_constant=scale_constant,
                resamples=resamples,
                confidence=confidence,
                seed=seed,
                minimum_spread=minimum_spread,
            )
            for member in current
        ]
        comparisons.extend(verdicts)
        if all(verdict.separated for verdict in verdicts):
            tiers.append([candidate])
        else:
            current.append(candidate)
    shared = len(set.intersection(*(set(item) for item in scores.values()))) if scores else 0
    return GatedRanking(
        tiers=tuple(tuple(tier) for tier in tiers),
        comparisons=tuple(comparisons),
        task_count=shared,
        planned_half_width=(resolution_half_width(shared, scale_constant=scale_constant) if shared > 0 else math.inf),
    )


def _mean(values: Iterable[float], metric_direction: str) -> float:
    collected = [higher_is_better(value, metric_direction) for value in values]
    return sum(collected) / len(collected) if collected else 0.0


def _percentile(sorted_values: Sequence[float], fraction: float) -> float:
    if not sorted_values:
        raise ValueError("no values")
    position = fraction * (len(sorted_values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[int(position)]
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def z_for_confidence(confidence: float) -> float:
    """Two-sided normal quantile for a confidence level."""
    if not 0 < confidence < 1:
        raise ValueError("confidence must be in (0, 1)")
    if abs(confidence - DEFAULT_CONFIDENCE) < 1e-9:
        return _Z95
    return statistics.NormalDist().inv_cdf(1 - (1 - confidence) / 2)
