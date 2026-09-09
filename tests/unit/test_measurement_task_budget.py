"""Iteration and selection are scored on different task sets (§3 item 3)."""

from __future__ import annotations

import pytest

from epistemic_loop.measurement.task_budget import TaskBudgetError, TaskBudgetPolicy

POOL = tuple(f"case{index:04d}" for index in range(400))


def test_the_defaults_are_the_ratio_the_campaign_measured() -> None:
    policy = TaskBudgetPolicy()

    assert (policy.iteration_tasks, policy.selection_tasks) == (32, 128)
    assert policy.throughput_ratio == 4.0
    assert policy.resolvable_difference("iteration") == pytest.approx(5.66, abs=0.01)
    assert policy.resolvable_difference("selection") == pytest.approx(2.83, abs=0.01)


def test_iteration_is_redrawn_every_round_and_selection_is_not() -> None:
    """A fixed iteration set is scored by the same agent every round and gets fitted; a moving
    selection set makes candidates from different rounds incomparable. Hence the asymmetry."""
    policy = TaskBudgetPolicy()

    assert policy.iteration_sample(POOL, round_index=1) != policy.iteration_sample(POOL, round_index=2)
    assert policy.iteration_sample(POOL, round_index=1) == policy.iteration_sample(POOL, round_index=1)
    assert policy.selection_sample(POOL) == policy.selection_sample(POOL)
    assert len(set(policy.selection_sample(POOL))) == 128


def test_a_purpose_that_cannot_see_the_difference_is_refused_before_the_round_is_run() -> None:
    policy = TaskBudgetPolicy()

    policy.audit("iteration", 10.0)  # 11 tasks needed, 32 available
    with pytest.raises(TaskBudgetError, match="needs 41 tasks"):
        policy.audit("iteration", 5.0)
    policy.audit("selection", 5.0)
    with pytest.raises(TaskBudgetError, match="needs 256 tasks"):
        policy.audit("selection", 2.0)


def test_required_tasks_grow_with_the_square_of_the_difference() -> None:
    policy = TaskBudgetPolicy()

    assert policy.required_tasks(10.0) == 11
    assert policy.required_tasks(5.0) == 41
    assert policy.required_tasks(2.5) == 164


def test_a_pool_too_small_for_the_requested_set_is_an_error_not_a_short_draw() -> None:
    policy = TaskBudgetPolicy()

    with pytest.raises(TaskBudgetError, match="distinct tasks"):
        policy.selection_sample(POOL[:100])


def test_malformed_policies_are_refused() -> None:
    with pytest.raises(ValueError):
        TaskBudgetPolicy(iteration_tasks=0)
    with pytest.raises(ValueError, match="smaller"):
        TaskBudgetPolicy(iteration_tasks=128, selection_tasks=32)
    with pytest.raises(ValueError):
        TaskBudgetPolicy(scale_constant=0)
    with pytest.raises(ValueError, match="unknown purpose"):
        TaskBudgetPolicy().tasks_for("ranking")
