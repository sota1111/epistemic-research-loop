"""IEEE-CIS experiment worker.

This is the *solver* side of the boundary: the research loop decides what to run and why, files an
`ExperimentRequest`, and this script executes exactly that request and writes back metrics. It holds
no research state, reads no hypothesis, and makes no decision about what to try next.

What it offers is a vocabulary of *capabilities*, not a solution. Splits, feature blocks, model
families, and diagnostics are ordinary machine-learning options; which of them matter on this dataset
is what the research loop has to find out. Nothing here encodes a competition-specific answer.

Every mode writes `metrics.json`; the training modes also write `fold_metrics.json`,
`seed_metrics.json`, and `subgroup_metrics.json`, which is what lets the loop judge robustness rather
than a single number.

    python3 run_experiment.py --mode train --split time_holdout --features base --model lgbm
    python3 run_experiment.py --mode adversarial_validation
    python3 run_experiment.py --mode feature_auc --top 40
    python3 run_experiment.py --mode duplicate_scan --split time_holdout
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold, StratifiedKFold

TARGET = "isFraud"
KEY = "TransactionID"
TIME = "TransactionDT"
#: The dataset's own epoch offset. TransactionDT is seconds since an unstated reference point.
SECONDS_PER_DAY = 86_400

DEFAULT_DATA = Path(".data/ieee-cis/parquet")


# --------------------------------------------------------------------------- spec


@dataclass
class Spec:
    mode: str
    split: str
    features: str
    model: str
    seeds: list[int]
    folds: int
    sample: int
    holdout_fraction: float
    drop_columns: list[str]
    drop_prefixes: list[str]
    drop_random: int
    drop_random_seed: int
    group_column: str
    n_estimators: int
    learning_rate: float
    num_leaves: int
    min_child_samples: int
    feature_fraction: float
    top: int
    submit: bool
    data: Path
    output: Path
    extra: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        payload = {key: value for key, value in self.__dict__.items()}
        payload["data"] = str(self.data)
        payload["output"] = str(self.output)
        return payload


# ----------------------------------------------------------------------- loading


def load(spec: Spec, split: str = "train") -> pd.DataFrame:
    frame = pd.read_parquet(spec.data / f"{split}.parquet")
    if spec.sample and split == "train" and len(frame) > spec.sample:
        # Sub-sample by time order, never at random: a random subsample would destroy the temporal
        # structure that several hypotheses are about.
        frame = frame.sort_values(TIME).tail(spec.sample).reset_index(drop=True)
    return frame


def _uid(frame: pd.DataFrame) -> pd.Series:
    """A coarse client identifier built from stable account columns.

    Entity grouping is a standard technique for non-IID rows; whether these particular columns
    identify a client on this dataset is a question for an experiment, not an assumption.
    """
    parts = []
    for column in ("card1", "addr1", "P_emaildomain"):
        if column in frame.columns:
            parts.append(frame[column].astype(str))
    if not parts:
        return pd.Series(np.arange(len(frame)), index=frame.index).astype(str)
    return pd.Series(["|".join(values) for values in zip(*parts, strict=True)], index=frame.index)


# ---------------------------------------------------------------------- features


def build_features(frame: pd.DataFrame, spec: Spec, reference: pd.DataFrame | None = None) -> pd.DataFrame:
    """Turn the raw table into a numeric matrix under the requested feature policy.

    `reference` is the frame that encodings are fitted on. Passing the training rows keeps a
    frequency encoding from seeing the evaluation rows, which is itself a leakage control.
    """
    source = frame if reference is None else reference
    columns = [column for column in frame.columns if column not in {TARGET, KEY}]

    if spec.features in {"no_v", "minimal"}:
        columns = [column for column in columns if not column.startswith("V")]
    if spec.features == "minimal":
        columns = [column for column in columns if not column.startswith(("id_", "D", "C"))]
    if spec.features == "no_id":
        columns = [column for column in columns if not column.startswith("id_")]
    for dropped in spec.drop_columns:
        columns = [column for column in columns if column != dropped]
    if spec.drop_random:
        # Size-matched control for a block ablation: removing N columns chosen at random costs
        # whatever losing N columns costs, with no claim about which ones. An ablation that matches
        # this number was measuring block size, not information.
        generator = np.random.default_rng(spec.drop_random_seed)
        droppable = [column for column in columns if column != TIME]
        chosen = set(generator.choice(droppable, size=min(spec.drop_random, len(droppable)), replace=False))
        columns = [column for column in columns if column not in chosen]
    if spec.drop_prefixes:
        # Block-level ablation: remove a whole named family such as the D deltas or the C counters.
        prefixes = tuple(spec.drop_prefixes)
        columns = [column for column in columns if not column.startswith(prefixes)]

    built: dict[str, pd.Series] = {}
    for column in columns:
        values = frame[column]
        if str(values.dtype) == "category" or values.dtype == object:
            # Ordinal codes from the reference frame's categories; unseen levels become -1.
            categories = pd.Index(source[column].astype("category").cat.categories)
            codes = pd.Categorical(values.astype(str), categories=categories.astype(str)).codes
            built[column] = pd.Series(codes, index=frame.index, dtype="float32")
        else:
            built[column] = pd.to_numeric(values, errors="coerce").astype("float32")

    if spec.features in {"time_aware", "freq_enc", "uid_agg"} and TIME in frame.columns:
        seconds = frame[TIME].astype("float64")
        built["_hour"] = ((seconds / 3600) % 24).astype("float32")
        built["_dayofweek"] = ((seconds / SECONDS_PER_DAY) % 7).astype("float32")

    if spec.features in {"freq_enc", "uid_agg"}:
        for column in ("card1", "addr1", "P_emaildomain"):
            if column in frame.columns:
                counts = source[column].astype(str).value_counts()
                built[f"_freq_{column}"] = frame[column].astype(str).map(counts).fillna(0).astype("float32")

    if spec.features == "uid_agg" and "TransactionAmt" in frame.columns:
        identifier = _uid(frame)
        reference_id = _uid(source)
        amounts = pd.to_numeric(source["TransactionAmt"], errors="coerce")
        grouped = amounts.groupby(reference_id)
        for name, aggregate in (("mean", grouped.mean()), ("std", grouped.std()), ("count", grouped.count())):
            built[f"_uid_amt_{name}"] = identifier.map(aggregate).astype("float32")

    # Assemble once: inserting several hundred columns one at a time fragments the frame badly.
    matrix = pd.concat(built, axis=1) if built else pd.DataFrame(index=frame.index)
    return matrix.replace([np.inf, -np.inf], np.nan)


# ------------------------------------------------------------------------ splits


def make_splits(frame: pd.DataFrame, spec: Spec, seed: int) -> list[tuple[np.ndarray, np.ndarray]]:
    """Return (train_index, evaluation_index) pairs under the requested validation scheme."""
    target = frame[TARGET].to_numpy()
    order = np.argsort(frame[TIME].to_numpy(), kind="stable")

    if spec.split == "time_holdout":
        cut = int(len(order) * (1 - spec.holdout_fraction))
        return [(order[:cut], order[cut:])]

    if spec.split == "time_kfold":
        # Expanding window: every evaluation block is strictly later than everything it trains on.
        blocks = np.array_split(order, spec.folds + 1)
        return [(np.concatenate(blocks[: index + 1]), blocks[index + 1]) for index in range(spec.folds)]

    if spec.split == "group_time":
        # Both controls at once: hold out the latest block, then drop from it every row whose entity
        # was already seen in training. What remains is later in time *and* unseen as an entity.
        cut = int(len(order) * (1 - spec.holdout_fraction))
        train_index, candidate = order[:cut], order[cut:]
        identifier = _uid(frame).to_numpy()
        seen = set(identifier[train_index])
        eval_index = np.array([row for row in candidate if identifier[row] not in seen], dtype=int)
        if len(eval_index) < 500:
            raise ValueError(f"group_time left only {len(eval_index)} evaluation rows; widen the holdout")
        return [(train_index, eval_index)]

    if spec.split == "group_time_contemporaneous":
        # The control arm for `group_time`: identical evaluation rows, identical entity separation,
        # identical training-set size -- but the training rows may be drawn from the same period as
        # the evaluation block instead of only from before it. The single thing that varies is
        # whether the model was allowed to see contemporaneous data.
        cut = int(len(order) * (1 - spec.holdout_fraction))
        identifier = _uid(frame).to_numpy()
        seen = set(identifier[order[:cut]])
        eval_index = np.array([row for row in order[cut:] if identifier[row] not in seen], dtype=int)
        if len(eval_index) < 500:
            raise ValueError(f"group_time left only {len(eval_index)} evaluation rows; widen the holdout")
        evaluated_entities = set(identifier[eval_index])
        pool = np.array(
            [row for row in order if row not in set(eval_index) and identifier[row] not in evaluated_entities],
            dtype=int,
        )
        size = min(cut, len(pool))
        chosen = np.random.default_rng(seed).choice(pool, size=size, replace=False)
        return [(np.sort(chosen), eval_index)]

    if spec.split == "random_kfold":
        splitter = StratifiedKFold(n_splits=spec.folds, shuffle=True, random_state=seed)
        return list(splitter.split(np.zeros(len(frame)), target))

    if spec.split.startswith("group_"):
        column = spec.group_column or spec.split.removeprefix("group_")
        groups = _uid(frame) if column == "uid" else frame[column].astype(str)
        splitter = GroupKFold(n_splits=spec.folds)
        return list(splitter.split(np.zeros(len(frame)), target, groups=groups.to_numpy()))

    raise ValueError(f"unknown split strategy: {spec.split}")


# ------------------------------------------------------------------------ models


def fit_predict(
    train_x: pd.DataFrame,
    train_y: np.ndarray,
    eval_x: pd.DataFrame,
    spec: Spec,
    seed: int,
) -> tuple[np.ndarray, dict[str, float]]:
    if spec.model == "logistic":
        from sklearn.impute import SimpleImputer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler

        pipeline = make_pipeline(
            SimpleImputer(strategy="median"),
            StandardScaler(),
            LogisticRegression(max_iter=200, random_state=seed),
        )
        pipeline.fit(train_x, train_y)
        return pipeline.predict_proba(eval_x)[:, 1], {}

    import lightgbm as lgb

    model = lgb.LGBMClassifier(
        n_estimators=spec.n_estimators,
        learning_rate=spec.learning_rate,
        num_leaves=spec.num_leaves,
        min_child_samples=spec.min_child_samples,
        colsample_bytree=spec.feature_fraction,
        subsample=0.9,
        subsample_freq=1,
        random_state=seed,
        n_jobs=-1,
        verbose=-1,
    )
    model.fit(train_x, train_y)
    importance = dict(
        sorted(
            zip(train_x.columns, model.feature_importances_.astype(float), strict=True),
            key=lambda item: item[1],
            reverse=True,
        )[:25]
    )
    return model.predict_proba(eval_x)[:, 1], importance


# -------------------------------------------------------------------- diagnostics


def adversarial_validation(spec: Spec) -> dict[str, Any]:
    """Can a model tell train rows from test rows? AUC near 0.5 means the two look alike.

    This measures distribution shift without touching the label, so it costs nothing in terms of
    the evaluation signal and answers a question no leaderboard probe could answer as cheaply.
    """
    train = load(spec, "train")
    test = load(spec, "test")
    if spec.sample and len(test) > spec.sample:
        test = test.sort_values(TIME).tail(spec.sample).reset_index(drop=True)
    shared = [column for column in train.columns if column in test.columns and column != TARGET]
    combined = pd.concat([train[shared], test[shared]], ignore_index=True)
    label = np.concatenate([np.zeros(len(train)), np.ones(len(test))])
    # TransactionDT trivially separates train from test; the interesting question is what else does.
    spec_without_time = Spec(**{**spec.to_json(), "data": spec.data, "output": spec.output})
    spec_without_time.drop_columns = [*spec.drop_columns, TIME]
    matrix = build_features(combined, spec_without_time)

    splitter = StratifiedKFold(n_splits=3, shuffle=True, random_state=spec.seeds[0])
    scores, importances = [], []
    for train_index, eval_index in splitter.split(matrix, label):
        prediction, importance = fit_predict(
            matrix.iloc[train_index], label[train_index], matrix.iloc[eval_index], spec, spec.seeds[0]
        )
        scores.append(float(roc_auc_score(label[eval_index], prediction)))
        importances.append(importance)

    merged: dict[str, float] = {}
    for importance in importances:
        for name, value in importance.items():
            merged[name] = merged.get(name, 0.0) + value / len(importances)
    ranked = dict(sorted(merged.items(), key=lambda item: item[1], reverse=True)[: spec.top])
    return {
        "metrics": {"adversarial_auc": float(np.mean(scores)), "adversarial_auc_std": float(np.std(scores))},
        "detail": {"most_shifted_features": ranked, "fold_scores": scores},
    }


def feature_auc(spec: Spec) -> dict[str, Any]:
    """Univariate AUC per feature. A single feature that nearly solves the task is a leakage lead."""
    frame = load(spec, "train")
    target = frame[TARGET].to_numpy()
    matrix = build_features(frame, spec)
    scores: dict[str, float] = {}
    for column in matrix.columns:
        values = matrix[column].to_numpy(dtype="float64")
        mask = ~np.isnan(values)
        if mask.sum() < 1000 or len(np.unique(values[mask])) < 2 or len(np.unique(target[mask])) < 2:
            continue
        scores[column] = float(roc_auc_score(target[mask], values[mask]))
    ranked = sorted(scores.items(), key=lambda item: abs(item[1] - 0.5), reverse=True)[: spec.top]
    return {
        "metrics": {
            "max_univariate_auc": float(max((abs(value - 0.5) + 0.5 for _, value in ranked), default=0.5)),
            "features_scored": float(len(scores)),
        },
        "detail": {"most_predictive_features": dict(ranked)},
    }


def duplicate_scan(spec: Spec) -> dict[str, Any]:
    """Do identical feature rows appear on both sides of the split boundary?

    Duplicates that straddle a split let a model memorise rather than generalise, which inflates the
    validation score without inflating the hidden score. That is a validation defect, not a model one.
    """
    frame = load(spec, "train")
    splits = make_splits(frame, spec, spec.seeds[0])
    train_index, eval_index = splits[0]
    matrix = build_features(frame, spec)
    subset = [column for column in matrix.columns if not column.startswith("_")][:40]
    fingerprint = matrix[subset].round(4).astype(str).agg("|".join, axis=1)
    train_keys = set(fingerprint.iloc[train_index])
    eval_keys = fingerprint.iloc[eval_index]
    overlap = float(eval_keys.isin(train_keys).mean())

    identifier = _uid(frame)
    entity_overlap = float(identifier.iloc[eval_index].isin(set(identifier.iloc[train_index])).mean())
    return {
        "metrics": {
            "row_duplicate_rate_across_split": overlap,
            "entity_overlap_rate_across_split": entity_overlap,
        },
        "detail": {"split": spec.split, "columns_hashed": len(subset)},
    }


# ------------------------------------------------------------------------ train


def _subgroup_scores(frame: pd.DataFrame, index: np.ndarray, target: np.ndarray, prediction: np.ndarray) -> dict:
    """AUC inside time buckets and product categories, so a localized gain cannot hide in a mean."""
    result: dict[str, dict[str, float]] = {}
    evaluated = frame.iloc[index]
    buckets = {
        "time_quartile": pd.qcut(evaluated[TIME], 4, labels=False, duplicates="drop"),
    }
    if "ProductCD" in evaluated.columns:
        buckets["product"] = evaluated["ProductCD"].astype(str)
    for name, series in buckets.items():
        scores: dict[str, float] = {}
        counts: dict[str, float] = {}
        for value in pd.unique(series.dropna()):
            mask = (series == value).to_numpy()
            if mask.sum() < 200 or len(np.unique(target[mask])) < 2:
                continue
            scores[str(value)] = float(roc_auc_score(target[mask], prediction[mask]))
            # A wide subgroup spread means nothing without the counts behind it: a small group's
            # AUC carries error bars a headline number hides.
            counts[str(value)] = float(mask.sum())
        if scores:
            result[name] = scores
            result[f"{name}_counts"] = counts
    return result


def train(spec: Spec) -> dict[str, Any]:
    frame = load(spec, "train")
    target_all = frame[TARGET].to_numpy()

    seed_scores: dict[str, float] = {}
    fold_scores: dict[str, list[float]] = {}
    subgroups: dict[str, Any] = {}
    importance_total: dict[str, float] = {}

    for seed in spec.seeds:
        splits = make_splits(frame, spec, seed)
        scores = []
        for position, (train_index, eval_index) in enumerate(splits):
            train_frame = frame.iloc[train_index]
            train_x = build_features(train_frame, spec, reference=train_frame)
            eval_x = build_features(frame.iloc[eval_index], spec, reference=train_frame)
            prediction, importance = fit_predict(train_x, target_all[train_index], eval_x, spec, seed)
            score = float(roc_auc_score(target_all[eval_index], prediction))
            scores.append(score)
            for name, value in importance.items():
                importance_total[name] = importance_total.get(name, 0.0) + value
            if position == 0 and seed == spec.seeds[0]:
                subgroups = _subgroup_scores(frame, eval_index, target_all[eval_index], prediction)
        fold_scores[str(seed)] = scores
        seed_scores[str(seed)] = float(np.mean(scores))

    means = list(seed_scores.values())
    flattened = [score for scores in fold_scores.values() for score in scores]
    worst_group = min(
        (min(values.values()) for values in subgroups.values() if values),
        default=float(np.mean(means)),
    )
    metrics = {
        "roc_auc": float(np.mean(means)),
        "roc_auc_seed_std": float(np.std(means)),
        "roc_auc_fold_std": float(np.std(flattened)),
        "worst_subgroup_auc": float(worst_group),
        "worst_subgroup_gap": float(np.mean(means) - worst_group),
    }
    return {
        "metrics": metrics,
        "fold_metrics": {"folds": flattened, "by_seed": fold_scores},
        "seed_metrics": {"seeds": seed_scores},
        "subgroup_metrics": subgroups,
        "detail": {"top_features": dict(sorted(importance_total.items(), key=lambda item: item[1], reverse=True)[:25])},
    }


def feature_comparison(spec: Spec) -> dict[str, Any]:
    """Score one model under two feature policies and report the gap between them.

    The research kept needing an ablation cost measured against a baseline taken under *identical*
    conditions, and getting that from two separate experiments makes the two runs differ in seed
    draw, sample and worker version. Varying only the feature policy inside one process removes all
    of that, which is what an ablation claim actually rests on.
    """
    baseline = str(spec.extra.get("baseline_features", "base"))
    contrast = str(spec.extra.get("contrast_features", "no_v"))
    contrast_drop = [item for item in str(spec.extra.get("contrast_drop_prefixes", "")).split(",") if item.strip()]
    results = {}
    for name, features, drop in ((baseline, baseline, []), (contrast, contrast, contrast_drop)):
        variant = Spec(**{**spec.to_json(), "data": spec.data, "output": spec.output})
        variant.features = features
        variant.drop_prefixes = [*spec.drop_prefixes, *drop]
        results[name if not drop else f"{name}_drop_{'_'.join(drop)}"] = train(variant)
    keys = list(results)
    cost = results[keys[0]]["metrics"]["roc_auc"] - results[keys[1]]["metrics"]["roc_auc"]
    return {
        "metrics": {
            f"roc_auc_{keys[0]}": results[keys[0]]["metrics"]["roc_auc"],
            f"roc_auc_{keys[1]}": results[keys[1]]["metrics"]["roc_auc"],
            "ablation_cost": float(cost),
            "roc_auc": results[keys[0]]["metrics"]["roc_auc"],
        },
        "fold_metrics": {name: value["fold_metrics"]["folds"] for name, value in results.items()},
        "seed_metrics": {name: value["seed_metrics"]["seeds"] for name, value in results.items()},
        "subgroup_metrics": results[keys[0]]["subgroup_metrics"],
        "detail": {"baseline": keys[0], "contrast": keys[1], "model": spec.model},
    }


def split_comparison(spec: Spec) -> dict[str, Any]:
    """Score one model under two validation schemes and report the gap between them.

    This is the experiment that treats validation as the object of study rather than as the
    instrument: the number it returns is a property of the split, not of the model.
    """
    baseline = spec.extra.get("baseline_split", "random_kfold")
    contrast = spec.extra.get("contrast_split", "time_holdout")
    results = {}
    for name in (baseline, contrast):
        variant = Spec(**{**spec.to_json(), "data": spec.data, "output": spec.output})
        variant.split = name
        results[name] = train(variant)
    gap = results[baseline]["metrics"]["roc_auc"] - results[contrast]["metrics"]["roc_auc"]
    return {
        "metrics": {
            f"roc_auc_{baseline}": results[baseline]["metrics"]["roc_auc"],
            f"roc_auc_{contrast}": results[contrast]["metrics"]["roc_auc"],
            "validation_gap": float(gap),
            "roc_auc": results[contrast]["metrics"]["roc_auc"],
        },
        "fold_metrics": {name: value["fold_metrics"]["folds"] for name, value in results.items()},
        "seed_metrics": {name: value["seed_metrics"]["seeds"] for name, value in results.items()},
        "subgroup_metrics": results[contrast]["subgroup_metrics"],
        "detail": {"baseline_split": baseline, "contrast_split": contrast},
    }


# ------------------------------------------------------------------- submission


def write_submission(spec: Spec, destination: Path) -> dict[str, Any]:
    """Fit on all training rows and score the Kaggle test set.

    The research loop never calls this on its own; it is requested only when an experiment's
    preregistered question needs a leaderboard observation.
    """
    train_frame = load(spec, "train")
    test_frame = load(spec, "test")
    train_x = build_features(train_frame, spec, reference=train_frame)
    test_x = build_features(test_frame, spec, reference=train_frame)
    test_x = test_x.reindex(columns=train_x.columns, fill_value=np.nan)
    prediction, _ = fit_predict(train_x, train_frame[TARGET].to_numpy(), test_x, spec, spec.seeds[0])
    submission = pd.DataFrame({KEY: test_frame[KEY].to_numpy(), TARGET: prediction})
    submission.to_csv(destination / "submission.csv", index=False)
    return {"rows": int(len(submission)), "mean_prediction": float(prediction.mean())}


# ------------------------------------------------------------------------- main


MODES = {
    "train": train,
    "split_comparison": split_comparison,
    "feature_comparison": feature_comparison,
    "adversarial_validation": adversarial_validation,
    "feature_auc": feature_auc,
    "duplicate_scan": duplicate_scan,
}


def parse(argv: list[str] | None = None) -> Spec:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", default="train", choices=sorted(MODES))
    parser.add_argument("--split", default="time_holdout")
    parser.add_argument("--features", default="base")
    parser.add_argument("--model", default="lgbm", choices=["lgbm", "logistic"])
    parser.add_argument("--seeds", default="11")
    parser.add_argument("--folds", type=int, default=4)
    parser.add_argument("--sample", type=int, default=200_000, help="most recent N training rows; 0 uses all")
    parser.add_argument("--holdout-fraction", type=float, default=0.2)
    parser.add_argument("--drop-columns", default="")
    parser.add_argument("--drop-prefixes", default="", help="comma-separated column-name prefixes to ablate as a block")
    parser.add_argument(
        "--drop-random", type=int, default=0, help="size-matched control: drop N randomly chosen columns"
    )
    parser.add_argument("--drop-random-seed", type=int, default=7)
    parser.add_argument("--group-column", default="")
    parser.add_argument("--n-estimators", type=int, default=300)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--num-leaves", type=int, default=63)
    parser.add_argument("--min-child-samples", type=int, default=40)
    parser.add_argument("--feature-fraction", type=float, default=0.8)
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--submit", action="store_true", help="also write submission.csv from a full-train fit")
    parser.add_argument("--baseline-split", default="random_kfold")
    parser.add_argument("--contrast-split", default="time_holdout")
    parser.add_argument("--baseline-features", default="base")
    parser.add_argument("--contrast-features", default="no_v")
    parser.add_argument("--contrast-drop-prefixes", default="", help="prefixes dropped only in the contrast arm")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, default=None)
    arguments = parser.parse_args(argv)

    output = arguments.output or Path(os.environ.get("ERL_OUTPUT_DIR", "outputs"))
    return Spec(
        mode=arguments.mode,
        split=arguments.split,
        features=arguments.features,
        model=arguments.model,
        seeds=[int(value) for value in str(arguments.seeds).split(",") if value.strip()],
        folds=arguments.folds,
        sample=arguments.sample,
        holdout_fraction=arguments.holdout_fraction,
        drop_columns=[value for value in arguments.drop_columns.split(",") if value.strip()],
        drop_prefixes=[value for value in arguments.drop_prefixes.split(",") if value.strip()],
        drop_random=arguments.drop_random,
        drop_random_seed=arguments.drop_random_seed,
        group_column=arguments.group_column,
        n_estimators=arguments.n_estimators,
        learning_rate=arguments.learning_rate,
        num_leaves=arguments.num_leaves,
        min_child_samples=arguments.min_child_samples,
        feature_fraction=arguments.feature_fraction,
        top=arguments.top,
        submit=arguments.submit,
        data=arguments.data,
        output=output,
        extra={
            "baseline_split": arguments.baseline_split,
            "contrast_split": arguments.contrast_split,
            "baseline_features": arguments.baseline_features,
            "contrast_features": arguments.contrast_features,
            "contrast_drop_prefixes": arguments.contrast_drop_prefixes,
        },
    )


def main(argv: list[str] | None = None) -> None:
    spec = parse(argv)
    destination = Path(spec.output)
    destination.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    result = MODES[spec.mode](spec)
    submission_info = write_submission(spec, destination) if spec.submit else None
    elapsed = time.monotonic() - started

    (destination / "metrics.json").write_text(json.dumps(result["metrics"], indent=2, sort_keys=True), "utf-8")
    for name in ("fold_metrics", "seed_metrics", "subgroup_metrics"):
        (destination / f"{name}.json").write_text(json.dumps(result.get(name, {}), indent=2, sort_keys=True), "utf-8")
    manifest = {
        "spec": spec.to_json(),
        "mode": spec.mode,
        # The loop records the repository's base commit, which cannot distinguish two experiments
        # run against different versions of this worker -- and a research loop that asks for a new
        # capability mid-run produces exactly that. Hashing the source makes the difference visible.
        "worker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "wall_seconds": round(elapsed, 2),
        "detail": result.get("detail", {}),
        "submission": submission_info,
        "versions": {"numpy": np.__version__, "pandas": pd.__version__},
    }
    (destination / "run_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str), "utf-8")
    print(json.dumps({"metrics": result["metrics"], "wall_seconds": round(elapsed, 2)}, sort_keys=True))


if __name__ == "__main__":
    main()
