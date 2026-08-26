#!/usr/bin/env python3
"""Run full-row common first-level cross-fit and the representation/learner matrix.

Every representation receives the exact same expanding forward folds, embargo,
OOF rows, seeds, slice definitions, and metric implementation. Feature mappings
are fitted inside each fold. Jobs are executed serially and checkpoints make the
heavy run resumable without treating resource failures as hypothesis evidence.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from sklearn.metrics import mean_squared_error, roc_auc_score

from epistemic_loop.evaluation.primary_endpoint import spearman_rank_consistency
from epistemic_loop.oof.diversity import effective_rank
from epistemic_loop.plugins.ieee_cis_artifacts import canonical_ieee_cis_dataset_hash

KEY = "TransactionID"
TIME = "TransactionDT"
TARGET = "isFraud"
SECONDS_PER_DAY = 86_400
REPRESENTATIONS = ("canonical_base", "island_01_cycle_4", "island_02_cycle_2", "island_03_cycle_2")
DEFAULT_SEEDS = (17, 42, 20_260_826)


class FeatureModule(Protocol):
    def build_features(self, frame: pd.DataFrame, reference: pd.DataFrame, **kwargs: object) -> pd.DataFrame: ...

    def encode_pair(
        self, reference: pd.DataFrame, frame: pd.DataFrame, **kwargs: object
    ) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]: ...


@dataclass(frozen=True)
class CommonFold:
    fold: int
    train_index: np.ndarray[Any, np.dtype[np.int64]]
    valid_index: np.ndarray[Any, np.dtype[np.int64]]
    train_max_time: int
    valid_min_time: int


def common_forward_folds(
    frame: pd.DataFrame,
    *,
    horizons: int = 3,
    gap_days: float = 7.0,
    minimum_train_fraction: float = 0.40,
) -> tuple[CommonFold, ...]:
    if horizons < 3 or gap_days <= 0:
        raise ValueError("common cross-fit requires at least three horizons and a positive gap")
    ordered = frame.sort_values([TIME, KEY], kind="stable").reset_index(drop=True)
    if not ordered[KEY].equals(frame.reset_index(drop=True)[KEY]):
        raise ValueError("input must be stably sorted by TransactionDT and TransactionID")
    times = ordered[TIME].to_numpy(dtype="int64")
    boundaries = np.linspace(minimum_train_fraction, 1.0, horizons + 1)
    gap_seconds = round(gap_days * SECONDS_PER_DAY)
    folds: list[CommonFold] = []
    for fold in range(horizons):
        valid_start = math.floor(boundaries[fold] * len(frame))
        valid_end = math.floor(boundaries[fold + 1] * len(frame))
        valid_min_time = int(times[valid_start])
        train_end = int(np.searchsorted(times, valid_min_time - gap_seconds, side="left"))
        train_index = np.arange(train_end, dtype="int64")
        valid_index = np.arange(valid_start, valid_end, dtype="int64")
        if not len(train_index) or not len(valid_index):
            raise ValueError("common fold has an empty train or validation partition")
        folds.append(
            CommonFold(
                fold=fold,
                train_index=train_index,
                valid_index=valid_index,
                train_max_time=int(times[train_index[-1]]),
                valid_min_time=valid_min_time,
            )
        )
    return tuple(folds)


def _load_module(name: str, path: Path) -> FeatureModule:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module  # type: ignore[return-value]


def _feature_modules(worktree_root: Path) -> dict[str, FeatureModule]:
    paths = {
        "island_01_cycle_4": worktree_root / "island-01/src/experiments/island_01_amount_microstructure.py",
        "island_02_cycle_2": worktree_root / "island-02/src/experiments/island_02_anchor_candidate.py",
        "island_03_cycle_2": worktree_root / "island-03/src/experiments/island_03_context_amount.py",
    }
    return {name: _load_module(f"v031_{name}", path) for name, path in paths.items()}


def build_representation(
    name: str,
    reference: pd.DataFrame,
    validation: pd.DataFrame,
    modules: dict[str, FeatureModule],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if name == "island_01_cycle_4":
        train, valid, _ = modules[name].encode_pair(
            reference,
            validation,
            include_amount=True,
            include_missingness=True,
        )
        return train, valid
    if name == "island_02_cycle_2":
        module = modules[name]
        return (
            module.build_features(reference, reference, cycle=2),
            module.build_features(validation, reference, cycle=2),
        )
    module = modules["island_03_cycle_2"]
    contextual = name != "canonical_base"
    cycle = 2 if contextual else 1
    return (
        module.build_features(reference, reference, contextual=contextual, cycle=cycle),
        module.build_features(validation, reference, contextual=contextual, cycle=cycle),
    )


def _fit_predict(
    learner: str,
    train_x: pd.DataFrame,
    train_y: np.ndarray[Any, np.dtype[np.int8]],
    valid_x: pd.DataFrame,
    *,
    seed: int,
    estimators: int,
    threads: int,
) -> np.ndarray[Any, np.dtype[np.float64]]:
    if learner == "lightgbm":
        import lightgbm as lgb  # type: ignore[import-untyped]

        model = lgb.LGBMClassifier(
            objective="binary",
            n_estimators=estimators,
            learning_rate=0.04,
            num_leaves=47,
            min_child_samples=40,
            colsample_bytree=0.75,
            subsample=0.85,
            subsample_freq=1,
            reg_lambda=1.0,
            random_state=seed,
            n_jobs=threads,
            verbosity=-1,
        )
        model.fit(train_x, train_y)
        return np.asarray(model.predict_proba(valid_x)[:, 1], dtype="float64")
    if learner == "catboost":
        from catboost import CatBoostClassifier  # type: ignore[import-untyped]

        model = CatBoostClassifier(
            iterations=estimators,
            depth=7,
            learning_rate=0.04,
            loss_function="Logloss",
            eval_metric="AUC",
            random_seed=seed,
            thread_count=threads,
            verbose=False,
            allow_writing_files=False,
        )
        model.fit(train_x, train_y)
        return np.asarray(model.predict_proba(valid_x)[:, 1], dtype="float64")
    if learner == "logistic_sgd":
        from sklearn.impute import SimpleImputer
        from sklearn.linear_model import SGDClassifier
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler

        model = make_pipeline(
            SimpleImputer(strategy="median"),
            StandardScaler(),
            SGDClassifier(
                loss="log_loss",
                penalty="l2",
                alpha=1e-5,
                max_iter=max(20, estimators),
                tol=1e-3,
                random_state=seed,
                n_jobs=threads,
            ),
        )
        model.fit(train_x, train_y)
        return np.asarray(model.predict_proba(valid_x)[:, 1], dtype="float64")
    raise ValueError(f"unknown learner: {learner}")


def _known_new_slice(reference: pd.DataFrame, validation: pd.DataFrame) -> np.ndarray[Any, np.dtype[np.str_]]:
    columns = [item for item in ("card1", "addr1", "P_emaildomain") if item in reference]
    if not columns:
        return np.full(len(validation), "questionable", dtype="U12")
    reference_key = reference[columns].astype("string").fillna("<NA>").agg("|".join, axis=1)
    validation_key = validation[columns].astype("string").fillna("<NA>").agg("|".join, axis=1)
    counts = reference_key.value_counts()
    history = validation_key.map(counts).fillna(0).to_numpy()
    return np.where(history == 0, "new", np.where(history == 1, "questionable", "known"))


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _nested_simplex_blend(
    predictions: np.ndarray[Any, np.dtype[np.float64]],
    targets: np.ndarray[Any, np.dtype[np.int8]],
    folds: np.ndarray[Any, np.dtype[np.int8]],
) -> tuple[np.ndarray[Any, np.dtype[np.float64]], dict[str, list[float]]]:
    blended = np.zeros(len(targets), dtype="float64")
    weights_by_fold: dict[str, list[float]] = {}
    width = predictions.shape[1]
    for fold in sorted(np.unique(folds)):
        train = folds != fold
        valid = folds == fold
        weights = np.full(width, 1.0 / width)
        matrix = predictions[train]
        target = targets[train]
        for _ in range(400):
            gradient = 2.0 * matrix.T.dot(matrix.dot(weights) - target) / len(target)
            weights = _simplex_projection(weights - 0.2 * gradient)
        blended[valid] = predictions[valid].dot(weights)
        weights_by_fold[str(fold)] = weights.tolist()
    return blended, weights_by_fold


def _simplex_projection(values: np.ndarray[Any, np.dtype[np.float64]]) -> np.ndarray[Any, np.dtype[np.float64]]:
    ordered = np.sort(values)[::-1]
    cumulative = np.cumsum(ordered)
    candidates = np.nonzero(ordered - (cumulative - 1.0) / np.arange(1, len(values) + 1) > 0)[0]
    rho = int(candidates[-1]) + 1
    threshold = (cumulative[rho - 1] - 1.0) / rho
    return np.maximum(values - threshold, 0.0)


def run(arguments: argparse.Namespace) -> dict[str, object]:
    output = arguments.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    dataset_hash = canonical_ieee_cis_dataset_hash(arguments.data.resolve())
    train = pd.read_parquet(arguments.data.resolve() / "train.parquet")
    train = train.sort_values([TIME, KEY], kind="stable").reset_index(drop=True)
    if len(train) != 590_540:
        raise ValueError(f"full common cross-fit requires 590540 rows, observed {len(train)}")
    folds = common_forward_folds(train, horizons=3, gap_days=arguments.gap_days)
    seeds = tuple(int(item) for item in arguments.seeds.split(","))
    if len(seeds) < 3:
        raise ValueError("common cross-fit requires at least three seeds")
    learners = tuple(item.strip() for item in arguments.learners.split(",") if item.strip())
    representations = tuple(item.strip() for item in arguments.representations.split(",") if item.strip())
    active_cells = tuple(
        (representation, learner)
        for representation in representations
        for learner in learners
        if learner != "logistic_sgd" or representation == "canonical_base" or arguments.simple_model_all
    )
    modules = _feature_modules(arguments.worktree_root.resolve())
    fold_assignment = np.full(len(train), -1, dtype="int8")
    for fold in folds:
        fold_assignment[fold.valid_index] = fold.fold
    oof_index = np.flatnonzero(fold_assignment >= 0)
    pd.DataFrame(
        {
            KEY: train[KEY],
            TIME: train[TIME],
            "fold": fold_assignment,
            "is_oof": fold_assignment >= 0,
        }
    ).to_parquet(output / "common_fold_assignment.parquet", index=False)

    prediction_columns: dict[str, np.ndarray[Any, np.dtype[np.float64]]] = {}
    run_metrics: dict[str, Any] = {}
    for representation in representations:
        for fold in folds:
            reference = train.iloc[fold.train_index]
            validation = train.iloc[fold.valid_index]
            train_x, valid_x = build_representation(representation, reference, validation, modules)
            train_y = reference[TARGET].to_numpy(dtype="int8")
            for learner in learners:
                if (representation, learner) not in active_cells:
                    continue
                for seed in seeds:
                    candidate_id = f"{representation}__{learner}__seed_{seed}"
                    checkpoint = output / "checkpoints" / f"{candidate_id}__fold_{fold.fold}.parquet"
                    source_checkpoint = (
                        arguments.checkpoint_source.resolve()
                        / "checkpoints"
                        / f"{candidate_id}__fold_{fold.fold}.parquet"
                        if arguments.checkpoint_source is not None
                        else None
                    )
                    if checkpoint.is_file():
                        part = pd.read_parquet(checkpoint)
                        prediction = part["prediction"].to_numpy(dtype="float64")
                    elif source_checkpoint is not None and source_checkpoint.is_file():
                        part = pd.read_parquet(source_checkpoint)
                        prediction = part["prediction"].to_numpy(dtype="float64")
                    else:
                        prediction = _fit_predict(
                            learner,
                            train_x,
                            train_y,
                            valid_x,
                            seed=seed,
                            estimators=arguments.estimators,
                            threads=arguments.threads,
                        )
                        checkpoint.parent.mkdir(parents=True, exist_ok=True)
                        pd.DataFrame({KEY: validation[KEY].to_numpy(), "prediction": prediction}).to_parquet(
                            checkpoint, index=False
                        )
                    vector = prediction_columns.setdefault(candidate_id, np.full(len(train), np.nan))
                    vector[fold.valid_index] = prediction
                    run_metrics.setdefault(candidate_id, {"fold_auc": {}})["fold_auc"][str(fold.fold)] = float(
                        roc_auc_score(validation[TARGET], prediction)
                    )
            del train_x, valid_x

    oof = pd.DataFrame(
        {
            KEY: train[KEY].iloc[oof_index].to_numpy(),
            TARGET: train[TARGET].iloc[oof_index].to_numpy(),
            "fold": fold_assignment[oof_index],
        }
    )
    for candidate_id, vector in prediction_columns.items():
        if np.isnan(vector[oof_index]).any():
            raise ValueError(f"incomplete OOF checkpoint set for {candidate_id}")
        oof[candidate_id] = vector[oof_index]
        run_metrics[candidate_id]["mean_auc"] = float(roc_auc_score(oof[TARGET], oof[candidate_id]))
    oof.to_parquet(output / "common_oof_predictions.parquet", index=False)

    seed_averaged: dict[str, np.ndarray[Any, np.dtype[np.float64]]] = {}
    for representation, learner in active_cells:
        identifier = f"{representation}__{learner}"
        seed_averaged[identifier] = np.mean(
            [oof[f"{identifier}__seed_{seed}"].to_numpy(dtype="float64") for seed in seeds], axis=0
        )
    targets = oof[TARGET].to_numpy(dtype="int8")
    residual_matrix = [targets - predictions for predictions in seed_averaged.values()]
    identifiers = list(seed_averaged)
    residual_correlations = {
        f"{left}::{right}": float(np.corrcoef(residual_matrix[i], residual_matrix[j])[0, 1])
        for i, left in enumerate(identifiers)
        for j, right in enumerate(identifiers)
        if i < j
    }
    prediction_correlations = {
        f"{left}::{right}": float(np.corrcoef(seed_averaged[left], seed_averaged[right])[0, 1])
        for left, right in combinations(identifiers, 2)
    }
    ranking_contexts = {
        f"seed_{seed}_fold_{fold.fold}": [
            float(run_metrics[f"{identifier}__seed_{seed}"]["fold_auc"][str(fold.fold)]) for identifier in identifiers
        ]
        for seed in seeds
        for fold in folds
    }
    rank_correlations = [
        correlation
        for left, right in combinations(ranking_contexts.values(), 2)
        if (correlation := spearman_rank_consistency(left, right)) is not None
    ]
    matrix = np.column_stack([seed_averaged[item] for item in identifiers])
    blended, fold_weights = _nested_simplex_blend(matrix, targets, oof["fold"].to_numpy(dtype="int8"))
    candidate_auc = {item: float(roc_auc_score(targets, values)) for item, values in seed_averaged.items()}
    candidate_mse = {item: float(mean_squared_error(targets, values)) for item, values in seed_averaged.items()}
    best_auc = max(candidate_auc.values())
    best_mse = min(candidate_mse.values())
    nested_auc = float(roc_auc_score(targets, blended))
    nested_mse = float(mean_squared_error(targets, blended))
    effective_rank_by_learner = {
        learner: effective_rank(
            [
                targets - seed_averaged[f"{representation}__{learner}"]
                for representation in representations
                if (representation, learner) in active_cells
            ]
        )
        for learner in learners
        if sum((representation, learner) in active_cells for representation in representations) >= 2
    }
    effective_rank_by_representation = {
        representation: effective_rank(
            [
                targets - seed_averaged[f"{representation}__{learner}"]
                for learner in learners
                if (representation, learner) in active_cells
            ]
        )
        for representation in representations
        if sum((representation, learner) in active_cells for learner in learners) >= 2
    }
    representation_transfer = {
        representation: {
            learner: candidate_auc[f"{representation}__{learner}"] - candidate_auc[f"canonical_base__{learner}"]
            for learner in learners
            if (representation, learner) in active_cells and ("canonical_base", learner) in active_cells
        }
        for representation in representations
    }

    slice_rows: list[dict[str, object]] = []
    for fold in folds:
        labels = _known_new_slice(train.iloc[fold.train_index], train.iloc[fold.valid_index])
        valid_targets = train[TARGET].iloc[fold.valid_index].to_numpy(dtype="int8")
        offset = np.searchsorted(oof_index, fold.valid_index)
        for label in ("known", "new", "questionable"):
            mask = labels == label
            if mask.sum() < 2 or len(np.unique(valid_targets[mask])) < 2:
                continue
            row: dict[str, object] = {"fold": fold.fold, "slice": label, "rows": int(mask.sum())}
            for identifier, predictions in seed_averaged.items():
                row[identifier] = float(roc_auc_score(valid_targets[mask], predictions[offset][mask]))
            slice_rows.append(row)

    report: dict[str, object] = {
        "dataset_hash": dataset_hash,
        "train_rows": len(train),
        "oof_rows": len(oof),
        "folds": [
            {
                "fold": item.fold,
                "train_rows": len(item.train_index),
                "valid_rows": len(item.valid_index),
                "train_max_time": item.train_max_time,
                "valid_min_time": item.valid_min_time,
                "observed_gap_days": (item.valid_min_time - item.train_max_time) / SECONDS_PER_DAY,
            }
            for item in folds
        ],
        "seeds": seeds,
        "representations": representations,
        "learners": learners,
        "active_representation_learner_cells": active_cells,
        "per_seed_and_fold": run_metrics,
        "seed_averaged_auc": candidate_auc,
        "seed_averaged_mse": candidate_mse,
        "residual_correlations": residual_correlations,
        "prediction_correlations": prediction_correlations,
        "rank_stability": {
            "mean_pairwise_spearman": float(np.mean(rank_correlations)) if rank_correlations else None,
            "minimum_pairwise_spearman": float(np.min(rank_correlations)) if rank_correlations else None,
            "contexts": ranking_contexts,
        },
        "mean_residual_correlation": float(np.mean(list(residual_correlations.values()))),
        "residual_covariance_effective_rank": effective_rank(residual_matrix),
        "effective_rank_by_learner": effective_rank_by_learner,
        "effective_rank_by_representation": effective_rank_by_representation,
        "representation_transfer_auc_delta_vs_canonical": representation_transfer,
        "nested_ensemble": {
            "auc": nested_auc,
            "mse": nested_mse,
            "marginal_auc_gain_over_best_single": nested_auc - best_auc,
            "marginal_mse_gain_over_best_single": best_mse - nested_mse,
            "fold_weights": fold_weights,
        },
        "slice_complementarity": slice_rows,
    }
    _write_json(output / "common_crossfit_report.json", report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path(".data/ieee-cis/parquet"))
    parser.add_argument("--worktree-root", type=Path, default=Path(".state/worktrees/ieee-cis-v03"))
    parser.add_argument("--output", type=Path, default=Path(".runs/ieee-cis-v031-common-crossfit"))
    parser.add_argument("--representations", default=",".join(REPRESENTATIONS))
    parser.add_argument("--learners", default="lightgbm")
    parser.add_argument("--seeds", default=",".join(map(str, DEFAULT_SEEDS)))
    parser.add_argument("--gap-days", type=float, default=7.0)
    parser.add_argument("--estimators", type=int, default=120)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--checkpoint-source", type=Path)
    parser.add_argument("--simple-model-all", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(run(parse_args()), indent=2, sort_keys=True))
