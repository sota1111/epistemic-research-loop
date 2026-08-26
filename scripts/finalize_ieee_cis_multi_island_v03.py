#!/usr/bin/env python3
"""Finalize the v0.3 IEEE-CIS run from honest common OOF intersections."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import yaml
from sklearn.metrics import roc_auc_score

from epistemic_loop.controller.candidate_artifacts import CandidateArtifactValidator
from epistemic_loop.domain.models import OOFRecord
from epistemic_loop.oof.diversity import analyze
from epistemic_loop.oof.ensemble import build_cross_fitted_ensemble
from epistemic_loop.plugins.ieee_cis import IEEERunAcceptance

RUN_ID = "ieee-cis-v03-multi-island-20260826"
WORLD = "common_oof_intersection_second_level_time_folds"


def candidate_roots(worktree_root: Path) -> dict[str, Path]:
    return {
        "island-01": worktree_root / "island-01/results/v03-validation-r3",
        "island-02": worktree_root / "island-02/results/v03-validation-r2",
        "island-03": worktree_root / "island-03/results/v03-validation-r2",
    }


def mapping(path: Path) -> dict[str, object]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def normalized_oof(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path).rename(columns={"TransactionID": "row_id", "isFraud": "target"})
    required = {"row_id", "target", "prediction"}
    if not required.issubset(frame.columns):
        raise ValueError(f"OOF schema is missing {sorted(required - set(frame.columns))}")
    frame = frame.loc[frame["prediction"].notna(), list(required)].copy()
    frame["row_id"] = frame["row_id"].astype(str)
    if frame["row_id"].duplicated().any():
        raise ValueError("OOF row ids must be unique")
    return frame.set_index("row_id")


def common_records(
    roots: dict[str, Path],
    timeline: pd.DataFrame,
    candidate_ids: list[str],
) -> tuple[pd.DataFrame, list[OOFRecord]]:
    frames = {item: normalized_oof(roots[item] / "oof_predictions.parquet") for item in candidate_ids}
    common = set.intersection(*(set(frame.index) for frame in frames.values()))
    if len(common) < 300:
        raise ValueError(f"too few common honest OOF rows: {len(common)}")
    ordered = timeline.loc[timeline["row_id"].isin(common)].sort_values(["TransactionDT", "row_id"])
    blocks = np.array_split(np.arange(len(ordered)), 3)
    fold_by_row = {
        str(ordered.iloc[row_index]["row_id"]): str(fold_index)
        for fold_index, block in enumerate(blocks)
        for row_index in block
    }
    aligned = pd.DataFrame(
        {
            "row_id": ordered["row_id"].astype(str).to_numpy(),
            "TransactionDT": ordered["TransactionDT"].to_numpy(),
        }
    )
    records: list[OOFRecord] = []
    reference_target: np.ndarray | None = None
    for candidate_id, frame in frames.items():
        candidate = frame.loc[aligned["row_id"]]
        target = candidate["target"].to_numpy(dtype=float)
        if reference_target is not None and not np.array_equal(reference_target, target):
            raise ValueError("candidate OOF targets disagree")
        reference_target = target
        aligned[candidate_id] = candidate["prediction"].to_numpy(dtype=float)
        records.extend(
            OOFRecord(
                row_id=row_id,
                fold_id=fold_by_row[row_id],
                target=float(label),
                oof_prediction=float(prediction),
                timestamp=str(timestamp),
                validation_world=WORLD,
                candidate_id=candidate_id,
            )
            for row_id, timestamp, label, prediction in zip(
                aligned["row_id"],
                aligned["TransactionDT"],
                target,
                aligned[candidate_id],
                strict=True,
            )
        )
    if reference_target is None:
        raise ValueError("no OOF targets")
    aligned["target"] = reference_target
    aligned["fold"] = aligned["row_id"].map(fold_by_row)
    if any(group["target"].nunique() != 2 for _, group in aligned.groupby("fold")):
        raise ValueError("each common second-level fold must contain both labels")
    return aligned, records


def cross_fitted_auc(aligned: pd.DataFrame, fold_weights: dict[str, dict[str, float]]) -> float:
    predictions = [
        sum(weights[item] * float(row[item]) for item in weights)
        for (_, row), weights in zip(
            aligned.iterrows(),
            (fold_weights[str(fold)] for fold in aligned["fold"]),
            strict=True,
        )
    ]
    return float(roc_auc_score(aligned["target"], predictions))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, object]:
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    roots = candidate_roots(args.worktree_root.resolve())
    validator = CandidateArtifactValidator()
    artifact_status = {item: validator.validate(root).model_dump(mode="json") for item, root in roots.items()}
    if not all(value["valid"] for value in artifact_status.values()):
        raise ValueError(f"candidate artifact validation failed: {artifact_status}")
    hashes = {str(mapping(root / "candidate.yaml")["dataset_hash"]) for root in roots.values()}
    if len(hashes) != 1:
        raise ValueError(f"candidate dataset hashes disagree: {sorted(hashes)}")
    dataset_hash = hashes.pop()
    timeline = pd.read_parquet(
        args.data_root.resolve() / "train.parquet",
        columns=["TransactionID", "TransactionDT"],
    )
    timeline["row_id"] = timeline["TransactionID"].astype(str)

    all_aligned, all_records = common_records(roots, timeline, list(roots))
    diversity = analyze(all_records)
    all_ensemble = build_cross_fitted_ensemble(
        all_records,
        run_id=RUN_ID,
        ensemble_id="ENS-IEEE-CIS-V03-ALL",
    )
    all_scores = {item: float(roc_auc_score(all_aligned["target"], all_aligned[item])) for item in roots}
    all_scores[all_ensemble.id] = cross_fitted_auc(all_aligned, all_ensemble.fold_weights)

    # Island 03 preregistered removal when mean contextual gain was non-positive.
    eligible_ids = ["island-01", "island-02"]
    eligible_aligned, eligible_records = common_records(roots, timeline, eligible_ids)
    eligible_ensemble = build_cross_fitted_ensemble(
        eligible_records,
        run_id=RUN_ID,
        ensemble_id="ENS-IEEE-CIS-V03-DECISION-ELIGIBLE",
    )
    eligible_scores = {
        item: float(roc_auc_score(eligible_aligned["target"], eligible_aligned[item])) for item in eligible_ids
    }
    eligible_scores[eligible_ensemble.id] = cross_fitted_auc(
        eligible_aligned,
        eligible_ensemble.fold_weights,
    )

    test_frames: dict[str, pd.DataFrame] = {}
    reference_ids: list[int] | None = None
    for candidate_id in eligible_ids:
        frame = pd.read_parquet(roots[candidate_id] / "test_predictions.parquet")
        frame = frame.rename(columns={"row_id": "TransactionID"}).sort_values("TransactionID")
        ids = frame["TransactionID"].astype(int).tolist()
        if reference_ids is not None and ids != reference_ids:
            raise ValueError("eligible candidate test rows disagree")
        reference_ids = ids
        test_frames[candidate_id] = frame
    if reference_ids is None:
        raise ValueError("no eligible test predictions")
    blended = sum(
        eligible_ensemble.weights[item] * test_frames[item]["prediction"].to_numpy(dtype=float) for item in eligible_ids
    )
    submission = pd.DataFrame({"TransactionID": reference_ids, "isFraud": blended})
    submission_path = output / "locked_submission.csv"
    submission.to_csv(submission_path, index=False)

    acceptance = IEEERunAcceptance(
        validated_behavioral_client_proxies=0,
        forward_horizons=3,
        fold_safe_uid_candidates=0,
        known_new_client_slice=False,
        model_families=frozenset({"lightgbm"}),
        oof_candidates=3,
        ensemble_candidates=1,
        locked_submissions=1,
    )
    context_metrics = mapping(roots["island-03"] / "metrics.json")
    report: dict[str, object] = {
        "run_id": RUN_ID,
        "dataset_hash": dataset_hash,
        "hidden_or_private_evaluation_performed": False,
        "common_evaluation_warning": (
            "second-level evaluation on common honest OOF rows, not a full common first-level cross-fit"
        ),
        "all_candidate_common_oof": {
            "rows": len(all_aligned),
            "scores": all_scores,
            "residual_correlations": diversity.residual_correlations,
            "prediction_disagreements": diversity.prediction_disagreements,
            "covariance_effective_rank": diversity.covariance_effective_rank,
            "ensemble_marginal_mse_gain": all_ensemble.marginal_gain,
            "ensemble_weights": all_ensemble.weights,
        },
        "decision_binding": {
            "island-01": "candidate eligible; structural interpretation remains blocked by open debt",
            "island-02": "promotion threshold passed",
            "island-03": (
                "contextual feature hypothesis rejected; candidate excluded from decision-eligible final blend"
            ),
            "island-03-context-gain": context_metrics["context_gain"],
            "island-03-worst-horizon-gain": context_metrics["context_gain_worst_horizon"],
        },
        "decision_eligible_common_oof": {
            "candidate_ids": eligible_ids,
            "rows": len(eligible_aligned),
            "scores": eligible_scores,
            "ensemble": eligible_ensemble.model_dump(mode="json"),
        },
        "locked_submission": {
            "path": str(submission_path),
            "rows": len(submission),
            "sha256": file_sha256(submission_path),
        },
        "artifact_status": artifact_status,
        "ieee_acceptance": {
            "passed": acceptance.passed,
            "validated_behavioral_client_proxies": 0,
            "forward_horizons": 3,
            "fold_safe_uid_candidates": 0,
            "known_new_client_slice": False,
            "model_families": ["lightgbm"],
            "oof_candidates": 3,
            "ensemble_candidates": 1,
            "locked_submissions": 1,
        },
    }
    write_json(output / "final_report.json", report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worktree-root", type=Path, default=Path(".state/worktrees/ieee-cis-v03"))
    parser.add_argument("--data-root", type=Path, default=Path(".data/ieee-cis/parquet"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".runs/ieee-cis-v03-multi-island-20260826-final"),
    )
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(run(parse_args()), indent=2, sort_keys=True))
