#!/usr/bin/env python3
"""Build and freeze the v0.3.2 IEEE-CIS hidden-endpoint batch.

This script never reads leaderboard scores.  It refits the four locked archive
representations on all labelled rows, creates the preregistered W02 ensemble,
and writes immutable hashes before any submission command may be used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from epistemic_loop.evaluation.primary_endpoint import (
    FrozenSubmissionSpec,
    freeze_submission_batch,
    sha256_file,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_ieee_cis_v031_common_crossfit import (  # noqa: E402
    KEY,
    REPRESENTATIONS,
    TARGET,
    TIME,
    _feature_modules,
    _fit_predict,
    build_representation,
)

DEFAULT_SEEDS = (17, 42, 20_260_826)
EXPECTED_TEST_ROWS = 506_691


def _json_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _submission(
    path: Path, identifiers: np.ndarray[Any, np.dtype[Any]], predictions: np.ndarray[Any, np.dtype[Any]]
) -> None:
    if len(identifiers) != EXPECTED_TEST_ROWS or len(predictions) != EXPECTED_TEST_ROWS:
        raise ValueError("v0.3.2 hidden submissions require exactly 506691 test rows")
    if not np.isfinite(predictions).all() or ((predictions < 0) | (predictions > 1)).any():
        raise ValueError("submission predictions must be finite probabilities")
    pd.DataFrame({KEY: identifiers, TARGET: predictions}).to_csv(path, index=False)


def _load_w02(path: Path, identifiers: np.ndarray[Any, np.dtype[Any]]) -> np.ndarray[Any, np.dtype[np.float64]]:
    frame = pd.read_parquet(path)
    prediction_column = "prediction" if "prediction" in frame else TARGET
    aligned = pd.DataFrame({KEY: identifiers}).merge(
        frame[[KEY, prediction_column]], on=KEY, how="left", validate="one_to_one"
    )
    prediction = aligned[prediction_column].to_numpy(dtype="float64")
    if np.isnan(prediction).any():
        raise ValueError("W02 test predictions do not cover the frozen test identifiers")
    return prediction


def _mean_weights(report: dict[str, Any]) -> np.ndarray[Any, np.dtype[np.float64]]:
    by_fold = report["quality_eligible"]["nested_ensemble"]["weights_by_fold"]
    weights = np.mean(np.asarray([by_fold[key] for key in sorted(by_fold)], dtype="float64"), axis=0)
    return weights / weights.sum()


def prepare(arguments: argparse.Namespace) -> dict[str, Any]:
    root = arguments.repository_root.resolve()
    output = arguments.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    train = pd.read_parquet(arguments.data.resolve() / "train.parquet")
    test = pd.read_parquet(arguments.data.resolve() / "test.parquet")
    train = train.sort_values([TIME, KEY], kind="stable").reset_index(drop=True)
    test = test.sort_values([TIME, KEY], kind="stable").reset_index(drop=True)
    if len(train) != 590_540 or len(test) != EXPECTED_TEST_ROWS:
        raise ValueError("v0.3.2 final fit requires the complete IEEE-CIS train and test snapshots")
    identifiers = test[KEY].to_numpy()
    target = train[TARGET].to_numpy(dtype="int8")
    modules = _feature_modules(arguments.worktree_root.resolve())
    archive_predictions: dict[str, np.ndarray[Any, np.dtype[np.float64]]] = {}
    for representation in REPRESENTATIONS:
        checkpoint = output / "test_predictions" / f"{representation}.parquet"
        if checkpoint.is_file():
            prediction = _load_w02(checkpoint, identifiers)
        else:
            train_x, test_x = build_representation(representation, train, test, modules)
            seed_predictions = [
                _fit_predict(
                    "lightgbm",
                    train_x,
                    target,
                    test_x,
                    seed=seed,
                    estimators=arguments.estimators,
                    threads=arguments.threads,
                )
                for seed in DEFAULT_SEEDS
            ]
            prediction = np.mean(np.vstack(seed_predictions), axis=0)
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame({KEY: identifiers, "prediction": prediction}).to_parquet(checkpoint, index=False)
        archive_predictions[representation] = prediction

    w02 = _load_w02(arguments.w02_test_predictions.resolve(), identifiers)
    report = json.loads(arguments.predictive_report.resolve().read_text(encoding="utf-8"))
    weights = _mean_weights(report)
    expected_order = [f"archive:{name}__lightgbm" for name in REPRESENTATIONS] + ["candidate:workstream-02"]
    if report["quality_eligible"]["candidates"] != expected_order or len(weights) != len(expected_order):
        raise ValueError("quality-eligible report order no longer matches the preregistered ensemble")
    ensemble_matrix = np.column_stack([archive_predictions[name] for name in REPRESENTATIONS] + [w02])
    ensemble = ensemble_matrix.dot(weights)

    submissions = output / "submissions"
    submissions.mkdir(exist_ok=True)
    canonical_source = (root / arguments.canonical_submission).resolve()
    canonical = submissions / "01_canonical_baseline.csv"
    canonical.write_bytes(canonical_source.read_bytes())
    archive_best = submissions / "02_archive_best_single.csv"
    w02_submission = submissions / "03_workstream_02_single.csv"
    ensemble_submission = submissions / "04_archive_plus_w02_nested_ensemble.csv"
    _submission(archive_best, identifiers, archive_predictions["island_02_cycle_2"])
    _submission(w02_submission, identifiers, w02)
    _submission(ensemble_submission, identifiers, ensemble)

    common_fold_hash = sha256_file(arguments.common_fold_plan.resolve())
    selection_rule = {
        "archive_best": "highest pooled AUC in v0.3.1 locked full common cross-fit",
        "ensemble": "mean of three nested fold simplex weights learned before hidden access",
        "candidate_order": expected_order,
        "weights": weights.tolist(),
        "no_post_hidden_additions": True,
    }
    candidate_metadata = [
        {
            "submission_id": "canonical_baseline",
            "candidate_commit": "pre_v0.3_locked",
            "feature_manifest_sha256": None,
            "test_prediction_sha256": None,
            "submission_sha256": sha256_file(canonical),
        },
        {
            "submission_id": "archive_best_single",
            "candidate_commit": "30934412508604424398c92e134e8aeffc9637f2",
            "representation": "island_02_cycle_2",
            "feature_manifest_sha256": sha256_file(arguments.archive_best_feature_manifest.resolve()),
            "test_prediction_sha256": sha256_file(output / "test_predictions/island_02_cycle_2.parquet"),
            "submission_sha256": sha256_file(archive_best),
        },
        {
            "submission_id": "workstream_02_single",
            "candidate_commit": "4acb717059ca182030a2bdc724bd21f485bfec27",
            "classification": "USEFUL_REPRESENTATION_WITH_PREREGISTERED_SLICE_SUPPORT",
            "feature_manifest_sha256": sha256_file(arguments.w02_feature_manifest.resolve()),
            "test_prediction_sha256": sha256_file(arguments.w02_test_predictions.resolve()),
            "submission_sha256": sha256_file(w02_submission),
        },
        {
            "submission_id": "archive_plus_workstream_02_nested_ensemble",
            "candidate_commit": "selection_artifact",
            "feature_manifest_sha256": None,
            "test_prediction_sha256": _json_hash(
                {
                    "components": expected_order,
                    "weights": weights.tolist(),
                    "submissions": [sha256_file(path) for path in (archive_best, w02_submission)],
                }
            ),
            "submission_sha256": sha256_file(ensemble_submission),
        },
    ]
    extended_manifest = {
        "version": "0.3.2",
        "competition": "ieee-fraud-detection",
        "submission_order": [item["submission_id"] for item in candidate_metadata],
        "candidate_count": 4,
        "fold_plan_sha256": common_fold_hash,
        "selection_rule": selection_rule,
        "selection_rule_sha256": _json_hash(selection_rule),
        "candidates": candidate_metadata,
        "hidden_accessed_before_freeze": False,
    }
    extended_manifest["manifest_sha256"] = _json_hash(extended_manifest)
    _write_json(output / "preregistration.json", extended_manifest)

    relative = lambda path: str(path.resolve().relative_to(root))  # noqa: E731
    specs = (
        FrozenSubmissionSpec(
            "canonical_baseline",
            relative(canonical),
            sha256_file(canonical),
            "pre-v0.3 locked reference",
            0.9100926867546033,
            "group_time_forward_full_train",
            "ERL v031 frozen 01 canonical baseline",
        ),
        FrozenSubmissionSpec(
            "archive_best_single",
            relative(archive_best),
            sha256_file(archive_best),
            "v0.3.1 archive best single refit on full train",
            0.902962947332893,
            "full_common_first_level_crossfit",
            "ERL v032 frozen 02 archive best single",
        ),
        FrozenSubmissionSpec(
            "workstream_02_single",
            relative(w02_submission),
            sha256_file(w02_submission),
            "v0.3.1 quality complementary candidate",
            0.9097486721527712,
            "full_common_first_level_crossfit",
            "ERL v032 frozen 03 workstream 02 single",
        ),
        FrozenSubmissionSpec(
            "archive_plus_workstream_02_nested_ensemble",
            relative(ensemble_submission),
            sha256_file(ensemble_submission),
            "locked quality-eligible nested ensemble",
            0.9172134020442154,
            "nested_full_common_first_level_crossfit",
            "ERL v032 frozen 04 archive plus W02 ensemble",
        ),
    )
    batch = freeze_submission_batch(
        repository_root=root,
        competition="ieee-fraud-detection",
        submissions=specs,
        output_path=output / "frozen_batch.json",
    )
    return {"batch_sha256": batch.batch_sha256, "preregistration": extended_manifest}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--data", type=Path, default=Path(".data/ieee-cis/parquet"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worktree-root", type=Path, default=Path(".state/worktrees/ieee-cis-v03"))
    parser.add_argument("--predictive-report", type=Path, required=True)
    parser.add_argument("--w02-test-predictions", type=Path, required=True)
    parser.add_argument("--w02-feature-manifest", type=Path, required=True)
    parser.add_argument("--archive-best-feature-manifest", type=Path, required=True)
    parser.add_argument("--common-fold-plan", type=Path, required=True)
    parser.add_argument("--canonical-submission", type=Path, required=True)
    parser.add_argument("--estimators", type=int, default=250)
    parser.add_argument("--threads", type=int, default=8)
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(prepare(parse_args()), indent=2, sort_keys=True))
