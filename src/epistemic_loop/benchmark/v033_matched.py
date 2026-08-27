"""Sealed matched-budget execution protocol for the v0.3.3 B/B+/C trial."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass

from epistemic_loop.controller.resource_metering import (
    ArmBudgetState,
    ArmHardBudget,
    CgroupV2Meter,
    ObservedBudgetMatch,
    ResourceReservation,
    fixed_thread_environment,
)
from epistemic_loop.evaluation.v032 import SystemArm, SystemArmCapabilities
from epistemic_loop.evaluation.v033 import AblationOutputLock, SealedAblationBatch


@dataclass(frozen=True)
class MatchedRunRequest:
    run_id: str
    arm: SystemArm
    seed: int
    reservation: ResourceReservation


@dataclass(frozen=True)
class MatchedAblationPlan:
    requests: tuple[MatchedRunRequest, ...]
    arm_budget: ArmHardBudget
    policy_sha256: str
    prompt_sha256: str
    acceptance_sha256: str
    plan_sha256: str
    private_results_visible_during_run: bool = False

    @classmethod
    def build(
        cls,
        *,
        seeds: Sequence[int],
        arm_budget: ArmHardBudget,
        reservation: ResourceReservation,
        policy_sha256: str,
        prompt_sha256: str,
        acceptance_sha256: str,
    ) -> MatchedAblationPlan:
        if len(seeds) != 12 or len(set(seeds)) != 12:
            raise ValueError("v0.3.3 requires exactly 12 unique seeds per arm")
        # Round-robin ordering reduces machine-time drift without exposing scores.
        requests = tuple(
            MatchedRunRequest(f"{arm.value}-{seed}", arm, seed, reservation)
            for seed in seeds
            for arm in (SystemArm.B, SystemArm.B_PLUS, SystemArm.C)
        )
        stable = {
            "requests": [asdict(item) for item in requests],
            "arm_budget": asdict(arm_budget),
            "policy_sha256": policy_sha256,
            "prompt_sha256": prompt_sha256,
            "acceptance_sha256": acceptance_sha256,
            "private_results_visible_during_run": False,
        }
        digest = hashlib.sha256(
            json.dumps(stable, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()
        return cls(requests, arm_budget, policy_sha256, prompt_sha256, acceptance_sha256, digest)

    def capabilities(self, arm: SystemArm) -> SystemArmCapabilities:
        return SystemArmCapabilities.for_arm(arm)


@dataclass(frozen=True)
class MatchedRunOutcome:
    output_lock: AblationOutputLock
    token_count: int
    work_type: str
    avoided_invalid_decision: bool = False


@dataclass(frozen=True)
class MatchedExecutionResult:
    completed_runs: int
    stopped_runs: tuple[str, ...]
    states: tuple[ArmBudgetState, ...]
    observed_budget_match: ObservedBudgetMatch
    sealed_batch: SealedAblationBatch | None
    cgroup_isolated: bool
    private_evaluation_ready: bool


RunCallback = Callable[[MatchedRunRequest, dict[str, str]], MatchedRunOutcome]


class SequentialMatchedRunner:
    """Execute a sealed plan sequentially with observed cgroup accounting.

    A live comparison refuses the root/shared cgroup.  Tests and policy
    preflights may explicitly permit it, but such runs cannot become the
    primary IEEE-CIS result.
    """

    def __init__(self, meter: CgroupV2Meter, *, allow_unisolated_preflight: bool = False):
        self.meter = meter
        self.allow_unisolated_preflight = allow_unisolated_preflight

    def run(self, plan: MatchedAblationPlan, callback: RunCallback) -> MatchedExecutionResult:
        if not self.meter.isolated and not self.allow_unisolated_preflight:
            raise RuntimeError("live matched-budget execution requires a dedicated cgroup-v2 node")
        states = {arm: ArmBudgetState(arm, plan.arm_budget) for arm in SystemArm}
        outputs: list[AblationOutputLock] = []
        stopped: list[str] = []
        environment = fixed_thread_environment({})
        for request in plan.requests:
            state = states[request.arm]
            admission = state.admit(request.reservation)
            if not admission.admitted:
                stopped.append(request.run_id)
                continue
            before = self.meter.snapshot()
            outcome = callback(request, environment)
            after = self.meter.snapshot()
            if outcome.output_lock.arm is not request.arm or outcome.output_lock.seed != request.seed:
                raise ValueError("callback output does not match the sealed arm and seed")
            state.record(
                after.delta(before),
                tokens=outcome.token_count,
                work_type=outcome.work_type,
                avoided_invalid_decision=outcome.avoided_invalid_decision,
            )
            outputs.append(outcome.output_lock)
        ordered_states = tuple(states[arm] for arm in SystemArm)
        matched = ObservedBudgetMatch.assess(ordered_states)
        complete = len(outputs) == len(plan.requests) and not stopped
        batch = None
        if complete and matched.matched and self.meter.isolated:
            budget_hash = hashlib.sha256(
                json.dumps(asdict(plan.arm_budget), sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            observed_ledger_hash = hashlib.sha256(
                json.dumps(
                    [
                        {
                            "arm": state.arm,
                            "process_tree_cpu_seconds": state.used_process_tree_cpu_seconds,
                            "tokens": state.used_tokens,
                            "wall_clock_seconds": state.used_wall_clock_seconds,
                            "peak_memory_bytes": state.peak_memory_bytes,
                            "structure_maturation_cpu_seconds": state.structure_maturation_cpu_seconds,
                            "candidate_cpu_seconds": state.candidate_cpu_seconds,
                            "avoided_invalid_decisions": state.avoided_invalid_decisions,
                        }
                        for state in ordered_states
                    ],
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                ).encode()
            ).hexdigest()
            batch = SealedAblationBatch.freeze(
                outputs,
                policy_sha256=plan.policy_sha256,
                prompt_sha256=plan.prompt_sha256,
                budget_sha256=budget_hash,
                observed_resource_ledger_sha256=observed_ledger_hash,
                acceptance_sha256=plan.acceptance_sha256,
                realized_budget_match_verified=True,
            )
        return MatchedExecutionResult(
            completed_runs=len(outputs),
            stopped_runs=tuple(stopped),
            states=ordered_states,
            observed_budget_match=matched,
            sealed_batch=batch,
            cgroup_isolated=self.meter.isolated,
            private_evaluation_ready=batch is not None,
        )
