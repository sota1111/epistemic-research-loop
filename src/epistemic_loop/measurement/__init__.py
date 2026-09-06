"""Measurement discipline: what a comparison can see, and what it is allowed to claim.

Three rules, in the order `docs/v050_course_correction.md` §4 puts them:

1. :mod:`epistemic_loop.measurement.resolution` -- estimate the half-width before comparing, and
   return no ranking when the interval spans zero.
2. :mod:`epistemic_loop.measurement.task_budget` -- iterate on one task set, rank on another.
3. :mod:`epistemic_loop.measurement.task_scores` -- persist the raw per-task vector; the composite
   is derived.

And, for §4's "decide the number of individuals first",
:mod:`epistemic_loop.measurement.power` -- what an arm of a given size can actually see.
"""

from __future__ import annotations

from epistemic_loop.measurement.power import (
    ArmPlan,
    arm_size_for,
    measurement_spread,
    plan_arm,
    student_t_quantile,
    total_spread,
)
from epistemic_loop.measurement.resolution import (
    ComparisonVerdict,
    GatedRanking,
    ResolutionGateError,
    compare_pair,
    gated_ranking,
    paired_bootstrap_interval,
    paired_differences,
    required_task_count,
    resolution_half_width,
    scale_constant_from_spread,
)
from epistemic_loop.measurement.task_budget import TaskBudgetError, TaskBudgetPolicy
from epistemic_loop.measurement.task_scores import (
    DerivedMetricError,
    TaskScore,
    TaskScoreStore,
    composite_scores,
    per_task_composite,
    recompute,
)

__all__ = [
    "ArmPlan",
    "ComparisonVerdict",
    "DerivedMetricError",
    "GatedRanking",
    "ResolutionGateError",
    "TaskBudgetError",
    "TaskBudgetPolicy",
    "TaskScore",
    "TaskScoreStore",
    "arm_size_for",
    "compare_pair",
    "composite_scores",
    "gated_ranking",
    "paired_bootstrap_interval",
    "measurement_spread",
    "paired_differences",
    "per_task_composite",
    "plan_arm",
    "recompute",
    "required_task_count",
    "resolution_half_width",
    "scale_constant_from_spread",
    "student_t_quantile",
    "total_spread",
]
