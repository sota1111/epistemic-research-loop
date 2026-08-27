"""Unrestricted-resource, outcome-only B/B+/C execution protocol for v0.3.4."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass

from epistemic_loop.evaluation.v032 import SystemArm
from epistemic_loop.evaluation.v034 import (
    ArmPolicyHash,
    OutcomeOnlyResourcePolicy,
    V034ArmCapabilities,
    V034RunOutputLock,
    V034SealedOutcomeBatch,
)

V034_IEEE_CIS_BASE_COMMIT = "ac3b46975e5da64570fb79d6e1141bc5c7525d0f"

INFRASTRUCTURE_ONLY_COMPONENTS = (
    "artifact_validator",
    "common_forward_crossfit_runner",
    "sealed_evaluator",
    "global_validation_constraint_registry",
    "decision_audit",
    "semantic_overlap_classifier",
    "final_meta_selector",
    "branch_worktree_manager",
)

FORBIDDEN_CONTAMINATION = (
    "past_private_score",
    "past_agent_candidate",
    "past_global_best",
    "past_ensemble_weight",
    "winner_code",
    "winner_writeup",
    "competition_solution_feature",
)


@dataclass(frozen=True)
class OutcomeRunRequest:
    run_id: str
    arm: SystemArm
    outer_seed: int
    agents: int = 3
    adaptive_cycles: int = 3

    @property
    def branch_name(self) -> str:
        return f"validation/v034-{self.arm.value.lower()}-seed-{self.outer_seed}"


@dataclass(frozen=True)
class OutcomeOnlyPlan:
    requests: tuple[OutcomeRunRequest, ...]
    base_commit: str
    dataset_sha256: str
    fold_plan_sha256: str
    row_set_sha256: str
    prompt_sha256: str
    research_opportunity_sha256: str
    hidden_evaluator_sha256: str
    acceptance_sha256: str
    validation_constraint_sha256: str
    arm_policy_hashes: tuple[ArmPolicyHash, ...]
    resource_policy: OutcomeOnlyResourcePolicy
    plan_sha256: str
    private_results_visible_during_run: bool = False

    @classmethod
    def build(
        cls,
        *,
        outer_seeds: Sequence[int],
        dataset_sha256: str,
        fold_plan_sha256: str,
        row_set_sha256: str,
        prompt_sha256: str,
        research_opportunity_sha256: str,
        hidden_evaluator_sha256: str,
        acceptance_sha256: str,
        validation_constraint_sha256: str,
        base_commit: str = V034_IEEE_CIS_BASE_COMMIT,
        resource_policy: OutcomeOnlyResourcePolicy | None = None,
    ) -> OutcomeOnlyPlan:
        seeds = tuple(outer_seeds)
        if len(seeds) != 12 or len(set(seeds)) != 12:
            raise ValueError("v0.3.4 requires exactly 12 unique outer seeds")
        if base_commit != V034_IEEE_CIS_BASE_COMMIT:
            raise ValueError("v0.3.4 IEEE-CIS runs must start from the immutable clean base")
        requests = tuple(
            OutcomeRunRequest(f"{arm.value}-{seed}", arm, seed)
            for seed in seeds
            for arm in (SystemArm.B, SystemArm.B_PLUS, SystemArm.C)
        )
        policies = tuple(
            ArmPolicyHash(arm, _hash(asdict(V034ArmCapabilities.for_arm(arm))))
            for arm in (SystemArm.B, SystemArm.B_PLUS, SystemArm.C)
        )
        resources = resource_policy or OutcomeOnlyResourcePolicy()
        stable = {
            "requests": [asdict(item) for item in requests],
            "base_commit": base_commit,
            "dataset_sha256": dataset_sha256,
            "fold_plan_sha256": fold_plan_sha256,
            "row_set_sha256": row_set_sha256,
            "prompt_sha256": prompt_sha256,
            "research_opportunity_sha256": research_opportunity_sha256,
            "hidden_evaluator_sha256": hidden_evaluator_sha256,
            "acceptance_sha256": acceptance_sha256,
            "validation_constraint_sha256": validation_constraint_sha256,
            "arm_policy_hashes": [asdict(item) for item in policies],
            "resource_policy": asdict(resources),
            "private_results_visible_during_run": False,
        }
        return cls(
            requests,
            base_commit,
            dataset_sha256,
            fold_plan_sha256,
            row_set_sha256,
            prompt_sha256,
            research_opportunity_sha256,
            hidden_evaluator_sha256,
            acceptance_sha256,
            validation_constraint_sha256,
            policies,
            resources,
            _hash(stable),
        )

    def capabilities(self, arm: SystemArm) -> V034ArmCapabilities:
        return V034ArmCapabilities.for_arm(arm)

    def validate_information_boundary(self, context: Mapping[str, object]) -> None:
        context_keys = _nested_keys(context)
        contaminated = sorted(key for key in FORBIDDEN_CONTAMINATION if key in context_keys)
        if contaminated:
            raise PermissionError(f"v0.3.4 context contains forbidden solution evidence: {contaminated}")


@dataclass(frozen=True)
class DiagnosticResourceObservation:
    cpu_seconds: float | None = None
    peak_memory_bytes: int | None = None
    wall_clock_seconds: float | None = None
    llm_tokens: int | None = None
    used_for_selection: bool = False
    used_for_acceptance: bool = False

    def __post_init__(self) -> None:
        if self.used_for_selection or self.used_for_acceptance:
            raise ValueError("resource observations are diagnostic-only in v0.3.4")


@dataclass(frozen=True)
class OutcomeRunResult:
    output_lock: V034RunOutputLock
    resource_observation: DiagnosticResourceObservation = DiagnosticResourceObservation()


@dataclass(frozen=True)
class OutcomeRunFailure:
    run_id: str
    error_type: str
    message: str


@dataclass(frozen=True)
class OutcomeOnlyExecutionResult:
    completed_runs: int
    failures: tuple[OutcomeRunFailure, ...]
    output_locks: tuple[V034RunOutputLock, ...]
    sealed_batch: V034SealedOutcomeBatch | None
    hidden_evaluation_ready: bool
    resource_metrics_used: bool = False


OutcomeRunCallback = Callable[[OutcomeRunRequest], OutcomeRunResult]


class SequentialOutcomeOnlyRunner:
    """Isolate heavy jobs sequentially without imposing or comparing resource budgets."""

    def run(self, plan: OutcomeOnlyPlan, callback: OutcomeRunCallback) -> OutcomeOnlyExecutionResult:
        outputs: list[V034RunOutputLock] = []
        failures: list[OutcomeRunFailure] = []
        for request in plan.requests:
            try:
                result = callback(request)
                lock = result.output_lock
                if (
                    lock.arm is not request.arm
                    or lock.outer_seed != request.outer_seed
                    or lock.run_id != request.run_id
                ):
                    raise ValueError("callback output does not match the isolated run request")
                if result.resource_observation.used_for_selection or result.resource_observation.used_for_acceptance:
                    raise ValueError("resource observations affected an outcome decision")
                outputs.append(lock)
            except Exception as exc:  # noqa: BLE001 - all 36 outcomes must be audited, including failures
                failures.append(OutcomeRunFailure(request.run_id, type(exc).__name__, str(exc)))
        batch = None
        if len(outputs) == len(plan.requests) and not failures:
            batch = V034SealedOutcomeBatch.freeze(
                outputs,
                arm_policy_hashes=plan.arm_policy_hashes,
                prompt_sha256=plan.prompt_sha256,
                acceptance_sha256=plan.acceptance_sha256,
                validation_constraint_sha256=plan.validation_constraint_sha256,
                plan_sha256=plan.plan_sha256,
                hidden_evaluator_sha256=plan.hidden_evaluator_sha256,
            )
        return OutcomeOnlyExecutionResult(
            len(outputs),
            tuple(failures),
            tuple(outputs),
            batch,
            batch is not None,
        )


def _hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _nested_keys(value: object) -> set[str]:
    if isinstance(value, Mapping):
        return {str(key) for key in value} | {nested for item in value.values() for nested in _nested_keys(item)}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return {nested for item in value for nested in _nested_keys(item)}
    return set()
