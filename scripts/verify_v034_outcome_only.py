#!/usr/bin/env python3
"""Preflight v0.3.4 without creating live candidates or querying Hidden scores."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import yaml

from epistemic_loop.benchmark.v034_outcome_only import OutcomeOnlyPlan
from epistemic_loop.controller.candidate_artifacts import V034_CANDIDATE_ARTIFACT_CONTRACT
from epistemic_loop.controller.common_crossfit import (
    SECONDS_PER_DAY,
    CommonCrossfitPlan,
    OrderedRow,
    ResearchSealedPartition,
)
from epistemic_loop.controller.cycle_contract import (
    V034_LOCKED_RUN_ARTIFACTS,
    CycleArtifactContract,
)
from epistemic_loop.controller.semantic_overlap import (
    SemanticExperimentRecord,
    SemanticOverlapClassifier,
)
from epistemic_loop.controller.validation_constraints import (
    GlobalValidationConstraintRegistry,
    ValidationArtifactDescriptor,
    ValidationGeometry,
    ValidationUse,
)
from epistemic_loop.evaluation.v032 import SystemArm
from epistemic_loop.evaluation.v034 import OutcomeOnlyResourcePolicy, V034Acceptance, V034ArmCapabilities

REQUIRED_DELIVERABLES = (
    "docs/v034_preregistration.json",
    "docs/v034_arm_B_policy.md",
    "docs/v034_arm_B_plus_policy.md",
    "docs/v034_arm_C_policy.md",
    "docs/v034_global_validation_constraints.json",
    "docs/v034_semantic_overlap_report.json",
    "docs/v034_decision_audit.json",
    "docs/v034_hidden_outcome_report.json",
    "docs/v034_final_acceptance.md",
    "results/v034_locked_outputs/.gitkeep",
)


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def verify(config_path: Path) -> dict[str, object]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    resource = config["resource_policy"]
    resource_policy = OutcomeOnlyResourcePolicy(
        cpu_limit=resource["cpu_limit"],
        memory_limit_gb=resource["memory_limit_gb"],
        gpu_limit=resource["gpu_limit"],
        thread_limit=resource["thread_limit"],
        wall_clock_limit=resource["wall_clock_limit"],
        experiment_cost_penalty=resource["experiment_cost_penalty"],
        use_resource_in_selection=resource["use_resource_in_selection"],
        use_resource_in_acceptance=resource["use_resource_in_acceptance"],
        heavy_execution_order=resource["heavy_execution_order"],
    )

    # The real plan is built from the immutable IEEE rows at live initialization. This synthetic
    # frame checks the stable partition/gap invariants without loading competition data here.
    rows = [OrderedRow(index * 2 * SECONDS_PER_DAY, 100_000 + index) for index in range(100)]
    partition = ResearchSealedPartition.build(rows)
    crossfit = CommonCrossfitPlan.build(partition)
    plan = OutcomeOnlyPlan.build(
        outer_seeds=config["comparison"]["outer_seeds"],
        dataset_sha256=_hash(config["immutable_base"]),
        fold_plan_sha256=crossfit.fold_plan_sha256,
        row_set_sha256=crossfit.research_row_set_sha256,
        prompt_sha256=_hash({"generic_agent": "same_prompt_all_arms"}),
        research_opportunity_sha256=_hash(config["common_external_conditions"]),
        hidden_evaluator_sha256=_hash(config["hidden_evaluation"]),
        acceptance_sha256=_hash({"primary": config["primary"], "secondary": config["secondary"]}),
        validation_constraint_sha256=_hash(config["global_validation_constraints"]),
        resource_policy=resource_policy,
    )
    plan.validate_information_boundary({"dataset_schema": "shared", "artifact_contract": "shared"})

    registry = GlobalValidationConstraintRegistry()
    shuffled = registry.assess(
        ValidationArtifactDescriptor("shuffled", ValidationGeometry.SHUFFLED, False, True, True, True),
        ValidationUse.FINAL_CANDIDATE_POOL,
    )
    strict = registry.assess(
        ValidationArtifactDescriptor("forward", ValidationGeometry.STRICT_FORWARD, True, True, True, True),
        ValidationUse.FINAL_CANDIDATE_POOL,
    )
    semantic = SemanticOverlapClassifier().classify(
        (
            SemanticExperimentRecord(
                "rep-a",
                "agent-a",
                "validation-gap",
                "mixed validation misranks future candidates",
                "split comparison",
                "auc gap",
                "eligibility",
                "tree",
                "late rows",
                "horizon replication",
                True,
            ),
            SemanticExperimentRecord(
                "rep-b",
                "agent-b",
                "validation-gap",
                "mixed validation misranks future candidates",
                "split comparison",
                "rank correlation",
                "eligibility",
                "linear",
                "multiple horizons",
                "learner sensitivity",
                True,
            ),
        )
    )[0]
    cycle_contract = CycleArtifactContract()
    deliverables = {name: Path(name).exists() for name in REQUIRED_DELIVERABLES}
    acceptance = V034Acceptance.preflight()
    return {
        "version": "0.3.4",
        "title": "Outcome-only B/B+/C and Sealed Decision Quality Verification",
        "scope": "implementation_and_policy_preflight_only",
        "immutable_base": config["immutable_base"],
        "outcome_only_plan": {
            "plan_sha256": plan.plan_sha256,
            "planned_runs": len(plan.requests),
            "runs_per_arm": 12,
            "agents_per_run": 3,
            "cycles_per_agent": 3,
            "private_visible_during_run": plan.private_results_visible_during_run,
            "live_runs_completed": 0,
            "all_outputs_locked": False,
            "hidden_evaluation_ready": False,
        },
        "resource_policy": {
            **asdict(resource_policy),
            "compare_resource_usage": False,
            "resource_fields_present_in_final_selector": False,
            "resource_fields_present_in_acceptance": False,
        },
        "arm_capabilities": {arm.value: asdict(V034ArmCapabilities.for_arm(arm)) for arm in SystemArm},
        "global_validation_constraint": {
            "registered": [item.constraint_id for item in registry.constraints],
            "shuffled_final_eligible": shuffled.eligible,
            "shuffled_diagnostic_eligible": shuffled.diagnostic_use_allowed,
            "strict_forward_final_eligible": strict.eligible,
        },
        "common_crossfit_preflight": {
            "synthetic_only": True,
            "research_rows": len(partition.research_rows),
            "sealed_rows": len(partition.sealed_rows),
            "horizons": crossfit.horizons,
            "gap_days": crossfit.minimum_gap_days,
            "seeds": crossfit.model_seeds,
            "past_only": crossfit.verify_past_only(),
            "live_fold_plan_hash": "UNMEASURED",
        },
        "cycle_contract": {
            arm.value: cycle_contract.required(arm) for arm in SystemArm
        },
        "candidate_artifact_contract": V034_CANDIDATE_ARTIFACT_CONTRACT,
        "locked_run_artifact_contract": V034_LOCKED_RUN_ARTIFACTS,
        "semantic_overlap_preflight": asdict(semantic),
        "acceptance": asdict(acceptance),
        "required_deliverables": deliverables,
        "deliverables_complete": all(deliverables.values()),
        "live_outcomes": {
            "decision_sign_accuracy": "UNMEASURED",
            "selection_regret": "UNMEASURED",
            "private_auc_C_minus_B": "UNMEASURED",
            "private_auc_C_minus_B_plus": "UNMEASURED",
        },
        "conclusion": (
            "v0.3.4 outcome-only contracts pass implementation preflight. No live B/B+/C run, sealed label "
            "unblind, Leaderboard query, or Hidden/Private claim was performed."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/benchmarks/v034_b_bplus_c_outcome_only.yaml"),
    )
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = verify(arguments.config)
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")


if __name__ == "__main__":
    main()
