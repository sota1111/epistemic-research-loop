#!/usr/bin/env python3
"""Verify v0.3.3 contracts without querying IEEE-CIS Private scores."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import yaml

from epistemic_loop.benchmark.v033_matched import MatchedAblationPlan
from epistemic_loop.controller.resource_metering import (
    ArmHardBudget,
    CgroupV2Meter,
    ResourceReservation,
)
from epistemic_loop.controller.structure_validation import (
    ControlFamilyRole,
    SeedEvidenceDisposition,
    SeedStructureEvidence,
    StructureControlFamilyResult,
    StructurePromotionGateV2,
)
from epistemic_loop.evaluation.v033 import (
    ArchiveBreadthAssessment,
    ComponentEffectObservation,
    ComponentEffectPrediction,
    EffectSign,
    MechanismCalibration,
    V033Acceptance,
    ValidationFidelityDebt,
    VerificationStatus,
)


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def verify(config_path: Path) -> dict[str, object]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    resource = config["fixed_resources"]
    reserve = resource["finalization_reserve"]
    reservation = resource["next_run_reservation"]
    budget = ArmHardBudget(
        resource["process_tree_cpu_seconds_per_arm"],
        resource["llm_tokens_per_arm"],
        resource["wall_clock_seconds_per_arm"],
        reserve["process_tree_cpu_seconds"],
        reserve["llm_tokens"],
        reserve["wall_clock_seconds"],
    )
    plan = MatchedAblationPlan.build(
        seeds=config["seeds"],
        arm_budget=budget,
        reservation=ResourceReservation(
            reservation["process_tree_cpu_seconds"],
            reservation["llm_tokens"],
            reservation["wall_clock_seconds"],
        ),
        policy_sha256=_hash(config["arms"]),
        prompt_sha256=_hash({"prompts": "must_be_frozen_by_live_runner"}),
        acceptance_sha256=_hash({"primary": config["primary"], "secondary": config["secondary"]}),
    )
    meter = CgroupV2Meter.for_current_process()
    snapshot = meter.snapshot()
    breadth = ArchiveBreadthAssessment.assess(1.1165606113452033)
    predictions = (
        ComponentEffectPrediction(
            "missingness_topology", EffectSign.POSITIVE, 0.001, 0.01, 1, ("identity_absent",), True
        ),
        ComponentEffectPrediction("category_hash", EffectSign.POSITIVE, 0.001, 0.01, 2, ("all_common_oof",), True),
    )
    observations = (
        ComponentEffectObservation("missingness_topology", 0.002024677220532234, 2, ("identity_absent",), True),
        ComponentEffectObservation("category_hash", 0.023077400776082113, 1, ("all_common_oof",), True),
    )
    mechanism = MechanismCalibration.assess(predictions, observations)
    controls = (
        StructureControlFamilyResult("tuning-entity", ControlFamilyRole.THRESHOLD_TUNING, True, True),
        StructureControlFamilyResult("held-temporal", ControlFamilyRole.HELD_OUT_EVALUATION, True, True),
        StructureControlFamilyResult("held-random-link", ControlFamilyRole.HELD_OUT_EVALUATION, False, False),
    )
    gate = StructurePromotionGateV2()
    positive = gate.assess(
        tuple(SeedStructureEvidence(seed, SeedEvidenceDisposition.SUPPORTING_EVIDENCE) for seed in (17, 42, 20260826)),
        controls,
    )
    unstable_negative = gate.assess(
        (
            SeedStructureEvidence(17, SeedEvidenceDisposition.SUPPORTING_EVIDENCE),
            SeedStructureEvidence(42, SeedEvidenceDisposition.CONTRADICTING_EVIDENCE),
            SeedStructureEvidence(20260826, SeedEvidenceDisposition.CONTRADICTING_EVIDENCE),
        ),
        controls,
    )
    acceptance = V033Acceptance.from_v032_observations()
    fidelity = ValidationFidelityDebt(
        VerificationStatus.OPEN,
        VerificationStatus.PROVISIONAL_PASS,
        VerificationStatus.PARTIAL,
    )
    return {
        "version": "0.3.3",
        "title": "Incremental Value over Strong QD Verification",
        "scope": "implementation_and_sealed_policy_preflight",
        "v032_frozen_evidence": {
            "archive_best_private_auc": 0.909654,
            "w02_private_auc": 0.899993,
            "locked_ensemble_private_auc": 0.914784,
            "w02_standalone_gain": -0.009661,
            "ensemble_gain": 0.005130,
            "local_to_private_spearman": 0.4,
        },
        "acceptance": asdict(acceptance),
        "validation_fidelity_debt": asdict(fidelity),
        "archive_breadth": asdict(breadth),
        "mechanism_calibration": asdict(mechanism),
        "structure_promotion_v2": {
            "positive_control_promoted": positive.promoted,
            "positive_leave_one_seed_out": [asdict(item) for item in positive.leave_one_seed_out],
            "mixed_negative_promoted": unstable_negative.promoted,
            "mixed_negative_reasons": unstable_negative.reasons,
            "seed_level_terminal_promotion": False,
        },
        "matched_ablation": {
            "plan_sha256": plan.plan_sha256,
            "planned_runs": len(plan.requests),
            "runs_per_arm": 12,
            "common_seed_count": len(config["seeds"]),
            "private_visible_during_run": plan.private_results_visible_during_run,
            "live_runs_completed": 0,
            "all_outputs_locked": False,
            "private_evaluation_ready": False,
            "system_C_vs_B": "UNMEASURED",
            "system_C_vs_B_plus": "UNMEASURED",
        },
        "resource_environment": {
            "cgroup_v2_readable": True,
            "cgroup_path": str(meter.path),
            "dedicated_cgroup": meter.isolated,
            "live_matched_run_admitted": meter.isolated,
            "blocker": None if meter.isolated else "current process is attached to shared root cgroup",
            "cpu_usage_seconds_at_preflight": snapshot.cpu_usage_seconds,
            "memory_current_bytes_at_preflight": snapshot.memory_current_bytes,
            "memory_peak_bytes_at_preflight": snapshot.memory_peak_bytes,
        },
        "private_embargo": {
            "v032_private_use": "research_conclusion_only",
            "same_competition_feature_model_or_weight_tuning": "forbidden",
            "confirmatory_claim_requires_unused_competition": True,
        },
        "conclusion": (
            "v0.3.3 contracts pass preflight; the live 36-run matched-budget Private comparison remains UNMEASURED "
            "because this environment has no dedicated writable cgroup-v2 node and no 36 locked outputs were produced"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/benchmarks/v033_b_bplus_c_36run.yaml"))
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
