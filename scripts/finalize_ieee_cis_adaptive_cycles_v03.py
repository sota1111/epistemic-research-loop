#!/usr/bin/env python3
"""Audit three adaptive IEEE-CIS exploration cycles and lock the selected blend."""

from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from finalize_ieee_cis_multi_island_v03 import (
    common_records,
    cross_fitted_auc,
    file_sha256,
    mapping,
    write_json,
)
from sklearn.metrics import roc_auc_score

from epistemic_loop.controller.candidate_artifacts import CandidateArtifactValidator
from epistemic_loop.controller.diversity_control import (
    CollectiveCollapseDetector,
    semantic_similarity,
)
from epistemic_loop.domain.models import CollapseMetrics, SemanticExperimentSignature
from epistemic_loop.oof.diversity import analyze
from epistemic_loop.oof.ensemble import build_cross_fitted_ensemble
from epistemic_loop.plugins.ieee_cis import IEEERunAcceptance

RUN_ID = "ieee-cis-v03-adaptive-cycles-20260826"
CYCLES = (2, 3, 4)
AGENTS = ("island-01", "island-02", "island-03")
SELECTED_CYCLES = {"island-01": 4, "island-02": 2, "island-03": 2}


def candidate_roots(worktree_root: Path) -> dict[str, Path]:
    return {
        f"{agent}-c{cycle:02d}": worktree_root / agent / f"results/v03-adaptive-cycle-{cycle:02d}"
        for cycle in CYCLES
        for agent in AGENTS
    }


def report_paths(run_root: Path) -> dict[int, Path]:
    return {cycle: run_root / f"ieee-cis-v03-adaptive-cycle-{cycle:02d}-20260826/report.json" for cycle in CYCLES}


def _clusters(signatures: dict[str, SemanticExperimentSignature], threshold: float = 0.85) -> list[list[str]]:
    remaining = set(signatures)
    clusters: list[list[str]] = []
    while remaining:
        seed = min(remaining)
        remaining.remove(seed)
        members = {seed}
        frontier = [seed]
        while frontier:
            current = frontier.pop()
            attached = {
                item for item in remaining if semantic_similarity(signatures[current], signatures[item]) >= threshold
            }
            remaining -= attached
            members |= attached
            frontier.extend(attached)
        clusters.append(sorted(members))
    return sorted(clusters)


def semantic_audit(reports: dict[int, dict[str, Any]]) -> dict[str, Any]:
    signatures = {
        f"{agent}-c{cycle:02d}": SemanticExperimentSignature.model_validate(
            report["experiments"][agent]["semantic_signature"]
        )
        for cycle, report in reports.items()
        for agent in AGENTS
    }
    pairwise = {
        f"{left}::{right}": semantic_similarity(signatures[left], signatures[right])
        for left, right in combinations(sorted(signatures), 2)
    }
    clusters = _clusters(signatures)
    detector = CollectiveCollapseDetector()
    collapse = []
    for cycle in CYCLES:
        metrics = CollapseMetrics.model_validate(reports[cycle]["global_control"]["collapse_metrics"])
        decision = detector.assess(metrics)
        collapse.append(
            {
                "cycle": cycle,
                "collapsed": decision.collapsed,
                "active_conditions": decision.active_conditions,
                "actions": decision.actions,
            }
        )
    return {
        "clusters": clusters,
        "cluster_count": len(clusters),
        "duplicate_rate": 1 - len(clusters) / len(signatures),
        "pairwise_similarity": pairwise,
        "mean_pairwise_similarity": float(np.mean(list(pairwise.values()))),
        "max_pairwise_similarity": max(pairwise.values()),
        "collective_collapse_sequence": collapse,
    }


def selected_roots(roots: dict[str, Path]) -> dict[str, Path]:
    return {agent: roots[f"{agent}-c{SELECTED_CYCLES[agent]:02d}"] for agent in AGENTS}


def selected_test_blend(
    roots: dict[str, Path],
    weights: dict[str, float],
    output: Path,
) -> dict[str, object]:
    reference_ids: list[int] | None = None
    predictions: dict[str, np.ndarray[Any, np.dtype[np.float64]]] = {}
    for candidate_id, root in roots.items():
        frame = pd.read_parquet(root / "test_predictions.parquet")
        frame = frame.rename(columns={"row_id": "TransactionID"}).sort_values("TransactionID")
        ids = frame["TransactionID"].astype(int).tolist()
        if reference_ids is not None and ids != reference_ids:
            raise ValueError("selected candidate test rows disagree")
        reference_ids = ids
        predictions[candidate_id] = frame["prediction"].to_numpy(dtype=float)
    if reference_ids is None:
        raise ValueError("no selected test predictions")
    blended = sum(weights[item] * predictions[item] for item in roots)
    submission = pd.DataFrame({"TransactionID": reference_ids, "isFraud": blended})
    path = output / "locked_submission.csv"
    submission.to_csv(path, index=False)
    return {"path": str(path), "rows": len(submission), "sha256": file_sha256(path)}


def run(args: argparse.Namespace) -> dict[str, object]:
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    roots = candidate_roots(args.worktree_root.resolve())
    reports = {
        cycle: json.loads(path.read_text(encoding="utf-8"))
        for cycle, path in report_paths(args.run_root.resolve()).items()
    }
    validator = CandidateArtifactValidator()
    artifact_status = {item: validator.validate(root).model_dump(mode="json") for item, root in roots.items()}
    if not all(value["valid"] for value in artifact_status.values()):
        raise ValueError(f"candidate artifact validation failed: {artifact_status}")
    dataset_hashes = {str(mapping(root / "candidate.yaml")["dataset_hash"]) for root in roots.values()}
    if len(dataset_hashes) != 1:
        raise ValueError(f"candidate dataset hashes disagree: {sorted(dataset_hashes)}")
    dataset_hash = dataset_hashes.pop()
    timeline = pd.read_parquet(
        args.data_root.resolve() / "train.parquet",
        columns=["TransactionID", "TransactionDT"],
    )
    timeline["row_id"] = timeline["TransactionID"].astype(str)

    all_aligned, all_records = common_records(roots, timeline, list(roots))
    all_diversity = analyze(all_records)
    all_scores = {item: float(roc_auc_score(all_aligned["target"], all_aligned[item])) for item in roots}

    finalists = selected_roots(roots)
    selected_aligned, selected_records = common_records(finalists, timeline, list(finalists))
    selected_diversity = analyze(selected_records)
    ensemble = build_cross_fitted_ensemble(
        selected_records,
        run_id=RUN_ID,
        ensemble_id="ENS-IEEE-CIS-V03-ADAPTIVE-SELECTED",
    )
    selected_scores = {
        item: float(roc_auc_score(selected_aligned["target"], selected_aligned[item])) for item in finalists
    }
    selected_scores[ensemble.id] = cross_fitted_auc(selected_aligned, ensemble.fold_weights)
    best_single_id = max(finalists, key=lambda item: selected_scores[item])
    if selected_scores[ensemble.id] > selected_scores[best_single_id]:
        final_selection = "ensemble"
        final_weights = ensemble.weights
        final_score = selected_scores[ensemble.id]
    else:
        final_selection = best_single_id
        final_weights = {item: float(item == best_single_id) for item in finalists}
        final_score = selected_scores[best_single_id]
    locked = selected_test_blend(finalists, final_weights, output)

    acceptance = IEEERunAcceptance(
        validated_behavioral_client_proxies=0,
        forward_horizons=3,
        fold_safe_uid_candidates=0,
        known_new_client_slice=False,
        model_families=frozenset({"lightgbm"}),
        oof_candidates=len(roots),
        ensemble_candidates=1,
        locked_submissions=1,
    )
    report: dict[str, object] = {
        "run_id": RUN_ID,
        "cycles": list(CYCLES),
        "dataset_hash": dataset_hash,
        "hidden_or_private_evaluation_performed": False,
        "execution": {
            "experiment_count": len(roots),
            "completed": sum(
                report["experiments"][agent]["terminal_status"] == "COMPLETED"
                for report in reports.values()
                for agent in AGENTS
            ),
            "resource_failures": sum(
                report["experiments"][agent]["terminal_status"] == "FAILED_RESOURCE"
                for report in reports.values()
                for agent in AGENTS
            ),
            "wall_seconds": sum(
                float(report["experiments"][agent]["wall_seconds"]) for report in reports.values() for agent in AGENTS
            ),
            "all_parallel_probes_rejected_while_heavy_running": all(
                experiment["parallel_probe_for_next"] is None
                or experiment["parallel_probe_for_next"]["accepted"] is False
                for report in reports.values()
                for experiment in report["experiments"].values()
            ),
        },
        "semantic": semantic_audit(reports),
        "decision_trace": {
            "island-01": {
                "selected_cycle": 4,
                "reason": "missingness ablation improved all three horizons; structural claim remains unvalidated",
                "structural_classification": "USEFUL_ENCODING_UNVALIDATED_STRUCTURE",
                "validation_debt_open": True,
            },
            "island-02": {
                "selected_cycle": 2,
                "reason": "frequency-only Cycle 3 and anchor-consensus Cycle 4 both lost to Cycle 2",
            },
            "island-03": {
                "selected_cycle": 2,
                "reason": "robust-tail Cycle 3 and missingness-summary Cycle 4 violated paired support gates",
            },
        },
        "all_candidate_common_oof": {
            "rows": len(all_aligned),
            "scores": all_scores,
            "residual_correlations": all_diversity.residual_correlations,
            "prediction_disagreements": all_diversity.prediction_disagreements,
            "covariance_effective_rank": all_diversity.covariance_effective_rank,
        },
        "selected_common_oof": {
            "rows": len(selected_aligned),
            "scores": selected_scores,
            "residual_correlations": selected_diversity.residual_correlations,
            "prediction_disagreements": selected_diversity.prediction_disagreements,
            "covariance_effective_rank": selected_diversity.covariance_effective_rank,
            "ensemble": ensemble.model_dump(mode="json"),
        },
        "final_selection": {
            "selected": final_selection,
            "primary_metric": "common_oof_auc",
            "score": final_score,
            "weights": final_weights,
            "ensemble_rejected_when_auc_below_best_single": final_selection != "ensemble",
        },
        "artifact_status": artifact_status,
        "locked_submission": locked,
        "ieee_acceptance": {
            "passed": acceptance.passed,
            "validated_behavioral_client_proxies": 0,
            "forward_horizons": 3,
            "fold_safe_uid_candidates": 0,
            "known_new_client_slice": False,
            "model_families": ["lightgbm"],
            "oof_candidates": len(roots),
            "ensemble_candidates": 1,
            "locked_submissions": 1,
        },
        "source_reports": {str(cycle): str(path) for cycle, path in report_paths(args.run_root.resolve()).items()},
    }
    write_json(output / "final_report.json", report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worktree-root", type=Path, default=Path(".state/worktrees/ieee-cis-v03"))
    parser.add_argument("--data-root", type=Path, default=Path(".data/ieee-cis/parquet"))
    parser.add_argument("--run-root", type=Path, default=Path(".runs"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".runs/ieee-cis-v03-adaptive-cycles-final-20260826"),
    )
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(run(parse_args()), indent=2, sort_keys=True))
