#!/usr/bin/env python3
"""Combine frozen endpoint, common cross-fit, debt, and clean-replay evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from epistemic_loop.controller.stagnation import (
    ExplorationProgressSnapshot,
    ExplorationStagnationDetector,
    PredictiveCollapseDetector,
    PredictiveCollapseMetrics,
    PredictiveDiversityDebt,
    PredictiveDiversityDebtRegistry,
)
from epistemic_loop.evaluation.acceptance import V031AcceptanceReport
from epistemic_loop.plugins.ieee_cis import IEEERunAcceptance
from epistemic_loop.plugins.ieee_cis_artifacts import ColdReplayReliabilityGate


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _adaptive_best(worktree_root: Path, cycle: int) -> float:
    scores = []
    for agent in ("island-01", "island-02", "island-03"):
        path = worktree_root / agent / f"results/v03-adaptive-cycle-{cycle:02d}/candidate.yaml"
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        scores.append(float(value["validation"]["primary_score"]))
    return max(scores)


def run(arguments: argparse.Namespace) -> dict[str, object]:
    primary = _json(arguments.primary.resolve())
    crossfit = _json(arguments.crossfit.resolve())
    structure = _json(arguments.structure.resolve())
    cold = _json(arguments.cold_replay.resolve())
    learner_matrix = _json(arguments.learner_matrix.resolve())
    experiments = list(cold["experiments"].values())
    reliability = ColdReplayReliabilityGate(
        first_attempt_valid_artifact_rate=sum(item["artifact_valid"] for item in experiments) / len(experiments),
        resource_failure_rate=sum(item["terminal_status"] == "FAILED_RESOURCE" for item in experiments)
        / len(experiments),
        final_test_row_count=min(int(item["test_prediction_rows"]) for item in experiments),
        oof_honesty_passed=all(item["oof_honesty_passed"] for item in experiments),
    )

    collapse_metrics = PredictiveCollapseMetrics(
        candidate_count=len(crossfit["seed_averaged_auc"]),
        residual_effective_rank=float(crossfit["residual_covariance_effective_rank"]),
        mean_residual_correlation=float(crossfit["mean_residual_correlation"]),
        nested_ensemble_auc_gain=float(crossfit["nested_ensemble"]["marginal_auc_gain_over_best_single"]),
    )
    predictive = PredictiveCollapseDetector().assess(collapse_metrics)
    predictive_debt: PredictiveDiversityDebt | None = None
    if predictive.collapsed:
        registry = PredictiveDiversityDebtRegistry(arguments.predictive_debt_root.resolve())
        debt_id = "PDD-IEEE-CIS-V031-001"
        try:
            predictive_debt = registry.get(debt_id)
        except KeyError:
            predictive_debt = registry.open(
                PredictiveDiversityDebt(
                    debt_id=debt_id,
                    candidate_id="NEXT-COMMON-CROSSFIT-CANDIDATE",
                    preregistered_data_slice="PENDING_AGENT_PREREGISTRATION",
                    proposed_error_mechanism="PENDING_AGENT_PREREGISTRATION",
                    archive_residual_correlation_floor=min(
                        float(item) for item in crossfit["residual_correlations"].values()
                    ),
                    quality_floor=max(float(item) for item in crossfit["seed_averaged_auc"].values()) - 0.02,
                )
            )
    stagnation_detector = ExplorationStagnationDetector()
    stagnation = []
    best_so_far: float | None = None
    for cycle in (2, 3, 4):
        cycle_best = _adaptive_best(arguments.worktree_root.resolve(), cycle)
        best_so_far = cycle_best if best_so_far is None else max(best_so_far, cycle_best)
        decision = stagnation_detector.assess(
            ExplorationProgressSnapshot(
                cycle=cycle,
                qd_occupancy=3,
                validated_structure_count=0,
                best_accepted_primary_metric=best_so_far,
                open_validation_debt_count=1,
            )
        )
        stagnation.append(
            {
                "cycle": cycle,
                "stagnated": decision.stagnated,
                "consecutive_stagnant_cycles": decision.consecutive_stagnant_cycles,
                "active_conditions": decision.active_conditions,
            }
        )

    primary_by_id = {item["submission_id"]: item for item in primary["observations"]}
    baseline_private = float(primary_by_id["canonical_baseline"]["private_auc"])
    adaptive_private = float(primary_by_id["v03_cycle4_locked_island01"]["private_auc"])
    ieee = IEEERunAcceptance(
        validated_behavioral_client_proxies=0,
        forward_horizons=3,
        fold_safe_uid_candidates=0,
        known_new_client_slice=False,
        model_families=frozenset(str(item) for item in learner_matrix["learners"]),
        oof_candidates=9,
        ensemble_candidates=1,
        locked_submissions=1,
    )
    acceptance = V031AcceptanceReport.assess(
        control_plane_checks={
            "generic_agents": True,
            "branch_isolation": True,
            "semantic_diversity": True,
            "resource_safety": reliability.resource_failure_rate <= 0.05,
            "artifact_contract": reliability.first_attempt_valid_artifact_rate >= 0.95,
            "candidate_production": True,
            "final_lock": True,
        },
        structure_checks={
            "spontaneous_registration": True,
            "leverage_assessment": True,
            "maturation_fork": True,
            "validation_debt": True,
            "unvalidated_structure_not_shared": not structure["confirmed_fact_shareable"],
            "terminal_promotion_decision": structure["debt"]["status"] == "resolved",
        },
        ieee_cis=ieee,
        locked_private_auc=adaptive_private,
        matched_baseline_private_auc=baseline_private,
        baseline_is_matched=False,
        multi_seed_passed=len(crossfit["seeds"]) >= 3,
        multiple_competitions_passed=False,
        validated_high_leverage_structures=0,
    )
    report: dict[str, object] = {
        "version": "0.3.1",
        "primary_endpoint": primary,
        "primary_endpoint_improved_over_canonical_baseline": adaptive_private >= baseline_private,
        "common_crossfit_summary": {
            "train_rows": crossfit["train_rows"],
            "oof_rows": crossfit["oof_rows"],
            "seeds": crossfit["seeds"],
            "seed_averaged_auc": crossfit["seed_averaged_auc"],
            "residual_effective_rank": crossfit["residual_covariance_effective_rank"],
            "mean_residual_correlation": crossfit["mean_residual_correlation"],
            "nested_ensemble": crossfit["nested_ensemble"],
            "predictive_collapse": {
                "collapsed": predictive.collapsed,
                "active_conditions": predictive.active_conditions,
                "notification": predictive.notification,
                "predictive_diversity_debt": predictive_debt.__dict__ if predictive_debt else None,
            },
        },
        "learner_transfer_summary": {
            "learners": learner_matrix["learners"],
            "seed_averaged_auc": learner_matrix["seed_averaged_auc"],
            "effective_rank_all_cells": learner_matrix["residual_covariance_effective_rank"],
            "effective_rank_by_learner": learner_matrix["effective_rank_by_learner"],
            "effective_rank_by_representation": learner_matrix["effective_rank_by_representation"],
            "representation_transfer_auc_delta_vs_canonical": learner_matrix[
                "representation_transfer_auc_delta_vs_canonical"
            ],
            "nested_ensemble": learner_matrix["nested_ensemble"],
            "quality_floor": max(learner_matrix["seed_averaged_auc"].values()) - 0.02,
            "quality_eligible_candidates": [
                identifier
                for identifier, score in learner_matrix["seed_averaged_auc"].items()
                if score >= max(learner_matrix["seed_averaged_auc"].values()) - 0.02
            ],
            "diagnosis": (
                "learner changes create low-quality error diversity; representation differences "
                "remain collapsed within each learner"
            ),
        },
        "structure_debt_terminal": structure,
        "clean_replay_reliability": {**reliability.__dict__, "passed": reliability.passed},
        "exploration_stagnation": stagnation,
        "acceptance": {
            "control_plane": acceptance.control_plane.__dict__,
            "dynamic_structure_mechanism": acceptance.dynamic_structure_mechanism.__dict__,
            "ieee_cis_capability": acceptance.ieee_cis_capability.__dict__,
            "primary_endpoint": acceptance.primary_endpoint.__dict__,
            "generic_structure_success": acceptance.generic_structure_success,
        },
        "matched_v02_v03_comparison_authorized": False,
        "matched_comparison_blockers": [
            "IEEE-CIS capability acceptance has not passed.",
            "A second competition has not been evaluated.",
        ],
    }
    _write(arguments.output.resolve(), report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--primary",
        type=Path,
        default=Path(".runs/ieee-cis-v031-primary-endpoint/primary_endpoint_results.json"),
    )
    parser.add_argument(
        "--crossfit",
        type=Path,
        default=Path(".runs/ieee-cis-v031-common-crossfit/common_crossfit_report.json"),
    )
    parser.add_argument(
        "--structure",
        type=Path,
        default=Path(".runs/ieee-cis-v031-structure-debt/terminal/terminal_report.json"),
    )
    parser.add_argument(
        "--cold-replay",
        type=Path,
        default=Path(".runs/ieee-cis-v031-cold-replay/report.json"),
    )
    parser.add_argument(
        "--learner-matrix",
        type=Path,
        default=Path(".runs/ieee-cis-v031-learner-matrix/common_crossfit_report.json"),
    )
    parser.add_argument("--worktree-root", type=Path, default=Path(".state/worktrees/ieee-cis-v03"))
    parser.add_argument("--output", type=Path, default=Path(".runs/ieee-cis-v031-final-report.json"))
    parser.add_argument(
        "--predictive-debt-root",
        type=Path,
        default=Path(".runs/ieee-cis-v031-predictive-diversity-debts"),
    )
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(run(parse_args()), indent=2, sort_keys=True))
