#!/usr/bin/env python3
"""Finalize the IEEE-CIS multi-island validation without consulting hidden scores."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from pathlib import Path
from statistics import fmean, pstdev
from typing import Any

import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import roc_auc_score

from epistemic_loop.controller.candidate_artifacts import CandidateArtifactValidator
from epistemic_loop.domain.models import CandidateArtifactRecord, CandidateDescriptors, OOFRecord
from epistemic_loop.oof.diversity import analyze
from epistemic_loop.plugins.ieee_cis import IEEERunAcceptance
from epistemic_loop.qd.candidate_archive import CandidateArchive
from epistemic_loop.qd.meta_selector import FinalMetaSelector, final_utility

RUN_ID = "ieee-cis-v02-multi-island-20260826"
VALIDATION_WORLD = "common_oof_intersection_second_level_time_folds"
TARGET = "isFraud"


def load_mapping(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def candidate_roots(worktree_root: Path) -> dict[str, Path]:
    agent_05_root = worktree_root / "agent-05/results/agent-05-entity-client-attempt-2"
    if not agent_05_root.is_dir():
        agent_05_root = worktree_root / "agent-05/results/agent-05-entity-client"
    return {
        "agent-04-temporal-causal-history": worktree_root / "agent-04/results/agent-04-temporal-causal-history",
        "agent-05-multiresolution-client-memory-v1": agent_05_root,
        "agent-06-forward-gap-family-gate": worktree_root / "agent-06/results/agent-06-forward-gap-family-gate",
    }


def aligned_oof(roots: dict[str, Path], data_root: Path) -> tuple[pd.DataFrame, list[OOFRecord]]:
    frames: dict[str, pd.DataFrame] = {}
    common: set[str] | None = None
    for candidate_id, root in roots.items():
        frame = pd.read_parquet(root / "oof_predictions.parquet", columns=["row_id", "target", "prediction"])
        frame = frame.loc[frame["prediction"].notna()].copy()
        frame["row_id"] = frame["row_id"].astype(str)
        frames[candidate_id] = frame.set_index("row_id")
        rows = set(frames[candidate_id].index)
        common = rows if common is None else common & rows
    if common is None or len(common) < 300:
        raise ValueError(f"too few common honest OOF rows: {0 if common is None else len(common)}")

    timeline = pd.read_parquet(
        data_root / "train.parquet",
        columns=["TransactionID", "TransactionDT", "card1", "addr1", "P_emaildomain"],
    )
    timeline["row_id"] = timeline["TransactionID"].astype(str)
    uid_columns = pd.DataFrame(
        {
            column: timeline[column].astype(object).where(timeline[column].notna(), "__MISSING__").astype(str)
            for column in ("card1", "addr1", "P_emaildomain")
        }
    )
    timeline["uid"] = uid_columns.agg("|".join, axis=1)
    common_timeline = timeline.loc[timeline["row_id"].isin(common), ["row_id", "TransactionDT", "uid"]]
    common_timeline = common_timeline.sort_values(["TransactionDT", "row_id"]).reset_index(drop=True)
    blocks = np.array_split(np.arange(len(common_timeline)), 3)
    fold_by_row = {
        str(common_timeline.iloc[index]["row_id"]): str(fold)
        for fold, indices in enumerate(blocks)
        for index in indices
    }
    client_slice_by_row: dict[str, str] = {}
    for indices in blocks:
        evaluation = common_timeline.iloc[indices]
        cutoff = float(evaluation["TransactionDT"].min()) - 7 * 86_400
        counts = timeline.loc[timeline["TransactionDT"] < cutoff, "uid"].value_counts()
        for _, row in evaluation.iterrows():
            count = int(counts.get(row["uid"], 0))
            client_slice_by_row[str(row["row_id"])] = "known" if count >= 2 else "questionable" if count == 1 else "new"
    ordered_rows = common_timeline["row_id"].tolist()
    reference_targets = frames[next(iter(frames))].loc[ordered_rows, "target"].astype(float)
    aligned = pd.DataFrame(
        {
            "row_id": ordered_rows,
            "TransactionDT": common_timeline["TransactionDT"].to_numpy(),
            "fold": [fold_by_row[row_id] for row_id in ordered_rows],
            "client_slice": [client_slice_by_row[row_id] for row_id in ordered_rows],
            "target": reference_targets.to_numpy(),
        }
    )
    records: list[OOFRecord] = []
    for candidate_id, frame in frames.items():
        candidate_targets = frame.loc[ordered_rows, "target"].astype(float).to_numpy()
        if not np.array_equal(candidate_targets, aligned["target"].to_numpy()):
            raise ValueError(f"target mismatch in common OOF rows for {candidate_id}")
        predictions = frame.loc[ordered_rows, "prediction"].astype(float).to_numpy()
        aligned[candidate_id] = predictions
        records.extend(
            OOFRecord(
                row_id=row_id,
                fold_id=fold_by_row[row_id],
                target=float(target),
                oof_prediction=float(prediction),
                timestamp=str(timestamp),
                subgroup_id=client_slice_by_row[row_id],
                validation_world=VALIDATION_WORLD,
                candidate_id=candidate_id,
            )
            for row_id, timestamp, target, prediction in zip(
                ordered_rows,
                aligned["TransactionDT"],
                aligned["target"],
                predictions,
                strict=True,
            )
        )
    for _, group in aligned.groupby("fold"):
        if group["target"].nunique() != 2:
            raise ValueError("each second-level fold must contain both fraud labels")
    return aligned, records


def slice_score(frame: pd.DataFrame, prediction_column: str, slice_name: str) -> float | None:
    values = []
    for _, fold in frame.groupby("fold", sort=True):
        subset = fold.loc[fold["client_slice"] == slice_name]
        if len(subset) and subset["target"].nunique() == 2:
            values.append(float(roc_auc_score(subset["target"], subset[prediction_column])))
    return fmean(values) if values else None


def standalone_records(roots: dict[str, Path], aligned: pd.DataFrame) -> list[CandidateArtifactRecord]:
    descriptors = {
        "agent-04-temporal-causal-history": ("agent-04", "temporal", "causal_client_history"),
        "agent-05-multiresolution-client-memory-v1": (
            "agent-05",
            "entity_client",
            "multi_resolution_client_memory",
        ),
        "agent-06-forward-gap-family-gate": ("agent-06", "model_family", "paired_family_gate"),
    }
    records = []
    for candidate_id, root in roots.items():
        candidate = load_mapping(root / "candidate.yaml")
        source_agent, niche, representation = descriptors[candidate_id]
        fold_scores = [
            float(roc_auc_score(group["target"], group[candidate_id]))
            for _, group in aligned.groupby("fold", sort=True)
        ]
        score = fmean(fold_scores)
        model_family = str(candidate.get("selected_family", "lightgbm"))
        records.append(
            CandidateArtifactRecord(
                candidate_id=candidate_id,
                source_agent=source_agent,
                git_commit=str(candidate["git_commit"]),
                dataset_hash=str(candidate["dataset_hash"]),
                environment_hash=str(candidate["environment_hash"]),
                artifact_root=str(root),
                descriptor=CandidateDescriptors(
                    validation_type=VALIDATION_WORLD,
                    model_family=model_family,
                    representation=representation,
                    error_profile=niche,
                    source_agent=source_agent,
                    epistemic_niche=niche,
                    validation_world=VALIDATION_WORLD,
                ),
                primary_score=score,
                score_std=pstdev(fold_scores),
                known_client_auc=slice_score(aligned, candidate_id, "known"),
                new_client_auc=slice_score(aligned, candidate_id, "new"),
                expected_forward_score=score,
                robustness=max(0, 1 - pstdev(fold_scores)),
                uncertainty=pstdev(fold_scores),
                leakage_check_passed=bool(candidate["leakage_check"]["passed"]),
                reproducibility_passed=bool(candidate["reproducibility"]["passed"]),
            )
        )
    return records


def ensemble_artifacts(
    final_root: Path,
    roots: dict[str, Path],
    aligned: pd.DataFrame,
    records: list[OOFRecord],
    dataset_hash: str,
) -> tuple[CandidateArtifactRecord, dict[str, Any]]:
    selector = FinalMetaSelector()
    ensemble = selector.build_ensemble(
        records,
        run_id=RUN_ID,
        ensemble_id="ENS-IEEE-CIS-V02-001",
        quality_floor_candidate_ids=list(roots),
    )
    root = final_root / "ensemble-candidate"
    if root.exists():
        raise FileExistsError(root)
    (root / "model_artifact").mkdir(parents=True)
    cross_fitted_predictions = []
    for _, row in aligned.iterrows():
        weights = ensemble.fold_weights[str(row["fold"])]
        cross_fitted_predictions.append(sum(weights[item] * float(row[item]) for item in ensemble.candidate_ids))
    aligned_ensemble = aligned[["row_id", "fold", "target", "TransactionDT", "client_slice"]].copy()
    aligned_ensemble["prediction"] = cross_fitted_predictions
    fold_scores = [
        float(roc_auc_score(group["target"], group["prediction"]))
        for _, group in aligned_ensemble.groupby("fold", sort=True)
    ]
    primary_score = fmean(fold_scores)

    test_frames = {}
    reference_rows: list[str] | None = None
    for candidate_id, candidate_root in roots.items():
        frame = pd.read_parquet(candidate_root / "test_predictions.parquet", columns=["row_id", "prediction"])
        frame["row_id"] = frame["row_id"].astype(str)
        frame = frame.sort_values("row_id").reset_index(drop=True)
        rows = frame["row_id"].tolist()
        if reference_rows is not None and rows != reference_rows:
            raise ValueError("test prediction rows are not aligned across candidates")
        reference_rows = rows
        test_frames[candidate_id] = frame["prediction"].to_numpy(dtype=float)
    if reference_rows is None:
        raise ValueError("no test predictions")
    test_prediction = sum(ensemble.weights[item] * test_frames[item] for item in ensemble.candidate_ids)
    test_output = pd.DataFrame({"row_id": reference_rows, "prediction": test_prediction})
    test_output.to_parquet(root / "test_predictions.parquet", index=False)
    pd.DataFrame({"TransactionID": np.asarray(reference_rows, dtype=np.int64), TARGET: test_prediction}).to_csv(
        root / "submission.csv", index=False
    )
    aligned_ensemble.to_parquet(root / "oof_predictions.parquet", index=False)
    aligned_ensemble[["row_id", "fold", "target", "TransactionDT", "client_slice"]].to_parquet(
        root / "fold_assignment.parquet", index=False
    )
    write_json(root / "model_artifact/weights.json", ensemble.model_dump(mode="json"))
    environment = {
        "python": platform.python_version(),
        "method": ensemble.method,
        "candidate_ids": ensemble.candidate_ids,
    }
    write_json(root / "environment_lock", environment)
    environment_hash = f"sha256:{sha256(root / 'environment_lock')}"
    script = Path(__file__).resolve()
    source = {
        "path": str(script),
        "sha256": sha256(script),
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        ).stdout.strip(),
    }
    write_json(root / "source_code_ref", source)
    features = [f"prediction::{item}" for item in ensemble.candidate_ids]
    write_json(root / "feature_manifest.yaml", {"features": features, "target_features": []})
    metrics = {
        "primary_score": primary_score,
        "score_std": pstdev(fold_scores),
        "common_oof_rows": len(aligned),
        "ensemble_cross_fitted_mse": ensemble.cross_fitted_loss,
        "best_single_mse": ensemble.best_single_loss,
        "marginal_ensemble_gain": ensemble.marginal_gain,
        "fold_scores": fold_scores,
        "weights": ensemble.weights,
        "fold_weights": ensemble.fold_weights,
    }
    write_json(root / "metrics.json", metrics)
    candidate = {
        "candidate_id": ensemble.id,
        "source_agent": "final-meta-selector",
        "git_commit": source["git_commit"],
        "dataset_hash": dataset_hash,
        "environment_hash": environment_hash,
        "validation": {
            "protocol": VALIDATION_WORLD,
            "primary_score": primary_score,
            "fold_scores": fold_scores,
            "score_std": pstdev(fold_scores),
        },
        "leakage_check": {
            "passed": True,
            "checks": {
                "weights_fit_from_oof_only": True,
                "second_level_fold_held_out": True,
                "test_labels_unavailable": True,
            },
        },
        "reproducibility": {"passed": True, "method": "deterministic simplex fit and recorded hashes"},
    }
    write_json(root / "candidate.yaml", candidate)
    write_json(
        root / "run_manifest.yaml",
        {
            "candidate_id": ensemble.id,
            "dataset_hash": dataset_hash,
            "environment_hash": environment_hash,
            "validation_world": VALIDATION_WORLD,
            "source_candidates": ensemble.candidate_ids,
        },
    )
    validation = CandidateArtifactValidator().validate(root)
    if not validation.valid:
        raise ValueError(f"ensemble artifact contract failed: {validation}")
    record = CandidateArtifactRecord(
        candidate_id=ensemble.id,
        source_agent="final-meta-selector",
        git_commit=source["git_commit"],
        dataset_hash=dataset_hash,
        environment_hash=environment_hash,
        artifact_root=str(root),
        descriptor=CandidateDescriptors(
            validation_type=VALIDATION_WORLD,
            model_family="oof_simplex_ensemble",
            representation="prediction_blend",
            error_profile="portfolio",
            source_agent="final-meta-selector",
            epistemic_niche="ensemble",
            validation_world=VALIDATION_WORLD,
        ),
        primary_score=primary_score,
        score_std=pstdev(fold_scores),
        known_client_auc=slice_score(aligned_ensemble, "prediction", "known"),
        new_client_auc=slice_score(aligned_ensemble, "prediction", "new"),
        expected_forward_score=primary_score,
        robustness=max(0, 1 - pstdev(fold_scores)),
        marginal_ensemble_gain=ensemble.marginal_gain,
        uncertainty=pstdev(fold_scores),
        leakage_check_passed=True,
        reproducibility_passed=True,
    )
    return record, ensemble.model_dump(mode="json")


def run(args: argparse.Namespace) -> dict[str, Any]:
    final_root = args.run_root.resolve() / args.final_name
    if final_root.exists():
        raise FileExistsError(final_root)
    roots = candidate_roots(args.worktree_root.resolve())
    validator = CandidateArtifactValidator()
    artifact_status = {
        candidate_id: validator.validate(root).model_dump(mode="json") for candidate_id, root in roots.items()
    }
    if not all(item["valid"] for item in artifact_status.values()):
        raise ValueError(f"standalone candidate artifact gate failed: {artifact_status}")
    dataset_hashes = {load_mapping(root / "candidate.yaml")["dataset_hash"] for root in roots.values()}
    if len(dataset_hashes) != 1:
        raise ValueError(f"candidate dataset hashes disagree: {sorted(dataset_hashes)}")
    dataset_hash = str(dataset_hashes.pop())
    aligned, oof_records = aligned_oof(roots, args.data_root.resolve())
    diversity = analyze(oof_records)
    standalone = standalone_records(roots, aligned)
    ensemble_record, ensemble = ensemble_artifacts(final_root, roots, aligned, oof_records, dataset_hash)
    archive = CandidateArchive()
    for candidate in [*standalone, ensemble_record]:
        archive.promote(candidate)
    selector = FinalMetaSelector()
    selected = selector.select([*standalone, ensemble_record])
    locked = selector.lock_submission(selected, final_root / "locked")
    acceptance = IEEERunAcceptance(
        validated_uid_candidates=0,
        forward_horizons=3,
        fold_safe_uid_candidates=1,
        known_new_client_slice=True,
        model_families=frozenset({"lightgbm"}),
        oof_candidates=3,
        ensemble_candidates=1,
        locked_submissions=1,
    )
    common_scores = {item.candidate_id: item.primary_score for item in standalone}
    common_scores[ensemble_record.candidate_id] = ensemble_record.primary_score
    report = {
        "run_id": RUN_ID,
        "hidden_or_private_evaluation_performed": False,
        "common_evaluation": {
            "protocol": VALIDATION_WORLD,
            "scope_warning": (
                "second-level evaluation on the intersection of independently generated honest OOF rows; "
                "this is not a full rerun of every pipeline on identical first-level folds"
            ),
            "row_count": len(aligned),
            "fold_count": int(aligned["fold"].nunique()),
            "client_slice_counts": aligned["client_slice"].value_counts().sort_index().to_dict(),
            "full_common_first_level_crossfit_completed": False,
            "scores": common_scores,
        },
        "diversity": {
            "residual_correlations": diversity.residual_correlations,
            "prediction_disagreements": diversity.prediction_disagreements,
            "covariance_effective_rank": diversity.covariance_effective_rank,
        },
        "ensemble": ensemble,
        "selection": {
            "candidate_id": selected.candidate_id,
            "utility": final_utility(selected),
            "locked_submission": str(locked.submission),
            "locked_sha256": locked.sha256,
        },
        "archive": {"candidate_count": len(archive.candidates), "occupancy": archive.occupancy},
        "artifact_status": artifact_status,
        "ieee_acceptance": {
            "passed": acceptance.passed,
            **acceptance.__dict__,
            "model_families": sorted(acceptance.model_families),
            "failed_reasons": [
                "no UID candidate satisfied all seven validation conditions",
                (
                    "only the LightGBM family was executed; GBDT and RF booster modes do not count "
                    "as two listed model families"
                ),
            ],
        },
    }
    write_json(final_root / "final_report.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=Path(".runs/ieee-cis-v02-multi-island-20260826"))
    parser.add_argument("--worktree-root", type=Path, default=Path(".state/worktrees/ieee-cis-v02"))
    parser.add_argument("--data-root", type=Path, default=Path(".data/ieee-cis/parquet"))
    parser.add_argument("--final-name", default="final")
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
