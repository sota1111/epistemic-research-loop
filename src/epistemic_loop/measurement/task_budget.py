"""Separate the task set you iterate on from the task set you rank on.

`docs/v050_course_correction.md` §3 item 3. One task set was used for everything: every iteration
paid the cost of the ranking set, and the ranking was still made on whatever the iteration set
happened to be. Splitting the two raised measured throughput four-fold
(`docs/v050_lessons.md` §1.1) because iteration only has to see the difference the *current change*
is expected to make, which is large, while ranking has to see the difference between neighbouring
candidates, which is small.

The two sets are drawn differently on purpose:

* the **iteration** set is redrawn every round. It is scored many times by the same agent, and a
  fixed set would be fitted to within a few rounds -- the same adaptive overfitting that
  `holdout/adaptivity.py` bounds for validation splits.
* the **selection** set is fixed for the whole campaign. Candidates from different rounds have to
  be comparable, and pairing (`measurement/resolution.py`) only cancels task difficulty when both
  candidates saw the *same* tasks.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

from epistemic_loop.measurement.resolution import (
    NEDO_SCALE_CONSTANT,
    required_task_count,
    resolution_half_width,
)


class TaskBudgetError(ValueError):
    """Raised when a task set is asked to carry a decision it is too small to carry."""


@dataclass(frozen=True)
class TaskBudgetPolicy:
    """How many tasks each purpose gets, and what each can therefore resolve.

    The defaults are the ones the loading campaign ended on: 32 for iteration, redrawn each round,
    and 128 for ranking. They are defaults for a 0-100 scoring scale with ``scale_constant``
    fitted at 32 points; on any other scoring system re-fit the constant before trusting the
    derived task counts (`resolution.scale_constant_from_spread`).
    """

    iteration_tasks: int = 32
    selection_tasks: int = 128
    scale_constant: float = NEDO_SCALE_CONSTANT

    def __post_init__(self) -> None:
        if self.iteration_tasks <= 0 or self.selection_tasks <= 0:
            raise ValueError("task counts must be positive")
        if self.selection_tasks < self.iteration_tasks:
            raise ValueError("the selection set must not be smaller than the iteration set")
        if self.scale_constant <= 0:
            raise ValueError("scale_constant must be positive")

    @property
    def throughput_ratio(self) -> float:
        """Iterations bought per ranking, all else equal."""
        return self.selection_tasks / self.iteration_tasks

    def resolvable_difference(self, purpose: str = "selection") -> float:
        return resolution_half_width(self.tasks_for(purpose), scale_constant=self.scale_constant)

    def tasks_for(self, purpose: str) -> int:
        if purpose == "iteration":
            return self.iteration_tasks
        if purpose == "selection":
            return self.selection_tasks
        raise ValueError(f"unknown purpose: {purpose}")

    def required_tasks(self, target_difference: float) -> int:
        return required_task_count(target_difference, scale_constant=self.scale_constant)

    def audit(self, purpose: str, target_difference: float) -> None:
        """Refuse a purpose whose task count cannot see the difference it is being asked about.

        Called before a round is designed, not after it is scored. The question it forces is the
        one §2.1 of the lessons says was never asked: what is the evidence that this axis moves the
        score by more than the measurement can see?
        """
        available = self.tasks_for(purpose)
        needed = self.required_tasks(target_difference)
        if needed > available:
            raise TaskBudgetError(
                f"{purpose} uses {available} tasks and resolves "
                f"{resolution_half_width(available, scale_constant=self.scale_constant):.2f}; "
                f"a difference of {target_difference:.2f} needs {needed} tasks"
            )

    def iteration_sample(self, pool: Sequence[str], *, round_index: int, seed: int = 0) -> tuple[str, ...]:
        """A fresh draw for one round. Two rounds with the same seed draw different tasks."""
        return self._draw(pool, self.iteration_tasks, seed=(seed, "iteration", round_index))

    def selection_sample(self, pool: Sequence[str], *, seed: int = 0) -> tuple[str, ...]:
        """The campaign's ranking set. Same pool and seed always give the same tasks."""
        return self._draw(pool, self.selection_tasks, seed=(seed, "selection"))

    def _draw(self, pool: Sequence[str], size: int, *, seed: object) -> tuple[str, ...]:
        unique = list(dict.fromkeys(pool))
        if len(unique) < size:
            raise TaskBudgetError(f"pool holds {len(unique)} distinct tasks; {size} were requested")
        return tuple(sorted(random.Random(repr(seed)).sample(unique, size)))
