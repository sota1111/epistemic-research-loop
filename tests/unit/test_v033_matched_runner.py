from __future__ import annotations

import pytest

from epistemic_loop.benchmark.v033_matched import (
    MatchedAblationPlan,
    MatchedRunOutcome,
    SequentialMatchedRunner,
)
from epistemic_loop.controller.resource_metering import (
    ArmHardBudget,
    CgroupV2Snapshot,
    ResourceReservation,
)
from epistemic_loop.evaluation.v033 import AblationOutputLock


class FakeMeter:
    def __init__(self, *, isolated: bool):
        self.isolated = isolated
        self.counter = 0

    def snapshot(self) -> CgroupV2Snapshot:
        value = self.counter
        self.counter += 1
        return CgroupV2Snapshot(value, value * 0.8, value * 0.2, 100, 200, value)


def _plan() -> MatchedAblationPlan:
    budget = ArmHardBudget(20, 1_000, 30, 2, 100, 2)
    return MatchedAblationPlan.build(
        seeds=tuple(range(12)),
        arm_budget=budget,
        reservation=ResourceReservation(1, 10, 1),
        policy_sha256="1" * 64,
        prompt_sha256="2" * 64,
        acceptance_sha256="3" * 64,
    )


def _callback(request: object, environment: dict[str, str]) -> MatchedRunOutcome:
    from epistemic_loop.benchmark.v033_matched import MatchedRunRequest

    assert isinstance(request, MatchedRunRequest)
    assert set(environment.values()) == {"2"}
    digest = "a" * 64
    lock = AblationOutputLock(
        request.run_id,
        request.arm,
        request.seed,
        digest,
        digest,
        digest,
        digest,
        digest,
        digest,
    )
    return MatchedRunOutcome(lock, 10, "structure_maturation" if request.arm.value == "C" else "candidate")


def test_matched_plan_is_36_runs_and_arm_capabilities_are_sealed() -> None:
    plan = _plan()

    assert len(plan.requests) == 36
    assert plan.private_results_visible_during_run is False
    assert not plan.capabilities(plan.requests[0].arm).hypothesis_registry
    with pytest.raises(ValueError, match="12 unique seeds"):
        MatchedAblationPlan.build(
            seeds=(1, 2, 3),
            arm_budget=plan.arm_budget,
            reservation=ResourceReservation(1, 1, 1),
            policy_sha256="1",
            prompt_sha256="2",
            acceptance_sha256="3",
        )


def test_live_runner_refuses_shared_root_cgroup() -> None:
    runner = SequentialMatchedRunner(FakeMeter(isolated=False))  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="dedicated cgroup"):
        runner.run(_plan(), _callback)


def test_complete_isolated_run_locks_batch_only_after_observed_budget_match() -> None:
    runner = SequentialMatchedRunner(FakeMeter(isolated=True))  # type: ignore[arg-type]
    result = runner.run(_plan(), _callback)

    assert result.completed_runs == 36
    assert result.observed_budget_match.matched
    assert result.private_evaluation_ready
    assert result.sealed_batch is not None
    assert result.sealed_batch.verify()
    c_state = next(state for state in result.states if state.arm.value == "C")
    assert c_state.opportunity_cost_cpu_fraction == 1.0


def test_unisolated_preflight_never_becomes_private_ready() -> None:
    runner = SequentialMatchedRunner(FakeMeter(isolated=False), allow_unisolated_preflight=True)  # type: ignore[arg-type]
    result = runner.run(_plan(), _callback)

    assert result.completed_runs == 36
    assert result.observed_budget_match.matched
    assert result.sealed_batch is None
    assert not result.private_evaluation_ready
