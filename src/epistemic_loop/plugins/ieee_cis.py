from __future__ import annotations

import hashlib
import itertools
import math
from collections import Counter, defaultdict
from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass
from statistics import fmean, pstdev
from typing import Any

from epistemic_loop.domain.models import FoldAssignment
from epistemic_loop.validation.splits import time_folds


@dataclass(frozen=True)
class UIDCandidate:
    name: str
    columns: tuple[str, ...]


@dataclass(frozen=True)
class UIDValidation:
    temporal_reappearance: bool
    feature_consistency: bool
    fraud_label_structure: bool
    beats_uid_free_generalization: bool
    reproduced_forward_folds: int
    fold_safe_aggregation_improves: bool
    frequency_artifact_rejected: bool

    @property
    def validated(self) -> bool:
        return all(
            (
                self.temporal_reappearance,
                self.feature_consistency,
                self.fraud_label_structure,
                self.beats_uid_free_generalization,
                self.reproduced_forward_folds >= 2,
                self.fold_safe_aggregation_improves,
                self.frequency_artifact_rejected,
            )
        )


@dataclass(frozen=True)
class IEEERunAcceptance:
    validated_uid_candidates: int
    forward_horizons: int
    fold_safe_uid_candidates: int
    known_new_client_slice: bool
    model_families: frozenset[str]
    oof_candidates: int
    ensemble_candidates: int
    locked_submissions: int

    @property
    def passed(self) -> bool:
        return (
            self.validated_uid_candidates >= 1
            and self.forward_horizons >= 3
            and self.fold_safe_uid_candidates >= 1
            and self.known_new_client_slice
            and len(self.model_families) >= 2
            and self.oof_candidates >= 3
            and self.ensemble_candidates >= 1
            and self.locked_submissions >= 1
        )


def generate_uid_candidates(columns: Sequence[str], *, maximum: int = 64) -> tuple[UIDCandidate, ...]:
    """Generate client identities from all IEEE-CIS structural families present."""

    available = set(columns)
    family_order: tuple[tuple[str, ...], ...] = (
        tuple(item for item in ("card1", "card2", "card3", "card4", "card5", "card6") if item in available),
        tuple(item for item in ("addr1", "addr2") if item in available),
        tuple(item for item in ("P_emaildomain", "R_emaildomain") if item in available),
        tuple(item for item in ("DeviceType", "DeviceInfo") if item in available),
        tuple(item for item in ("D1", "D2", "D4", "D10", "D15") if item in available),
        tuple(item for item in ("reference_date", "TransactionDT") if item in available),
    )
    candidates: dict[tuple[str, ...], UIDCandidate] = {}
    for base in family_order[0] or ():
        singleton_key = (base,)
        candidates[singleton_key] = UIDCandidate("uid_" + "_".join(singleton_key), singleton_key)
    non_empty = [family for family in family_order if family]
    for width in range(2, min(5, len(non_empty)) + 1):
        for families in itertools.combinations(non_empty, width):
            for values in itertools.product(*families):
                combined_key = tuple(dict.fromkeys(values))
                candidates.setdefault(
                    combined_key,
                    UIDCandidate("uid_" + "_".join(combined_key), combined_key),
                )
                if len(candidates) >= maximum:
                    return tuple(candidates.values())
    return tuple(candidates.values())


def uid_value(row: Mapping[str, Any], candidate: UIDCandidate) -> str:
    canonical = "|".join("<NA>" if row.get(column) is None else str(row.get(column)) for column in candidate.columns)
    return hashlib.sha256(canonical.encode()).hexdigest()[:24]


def multi_horizon_forward_folds(
    row_ids: Sequence[str],
    timestamps: Sequence[Any],
    *,
    horizons: int = 3,
    gap_rows: int = 1,
    world_id: str = "W-multi-horizon-time-gap",
) -> list[FoldAssignment]:
    if horizons < 3:
        raise ValueError("IEEE-CIS candidate validation requires at least three horizons")
    if gap_rows < 1:
        raise ValueError("IEEE-CIS forward validation requires a non-zero time gap")
    return time_folds(row_ids, timestamps, world_id=world_id, n_splits=horizons, gap_rows=gap_rows)


def rolling_window_forward_folds(
    row_ids: Sequence[str],
    timestamps: Sequence[Any],
    *,
    horizons: int = 3,
    gap_rows: int = 1,
    train_window_rows: int,
) -> list[FoldAssignment]:
    if train_window_rows < 1:
        raise ValueError("rolling train window must be positive")
    expanding = multi_horizon_forward_folds(row_ids, timestamps, horizons=horizons, gap_rows=gap_rows)
    return [fold.model_copy(update={"train_row_ids": fold.train_row_ids[-train_window_rows:]}) for fold in expanding]


def fold_safe_uid_aggregates(
    fit_rows: Sequence[Mapping[str, Any]],
    transform_rows: Sequence[Mapping[str, Any]],
    *,
    uid: UIDCandidate,
    amount_column: str = "TransactionAmt",
    time_column: str = "TransactionDT",
    aggregate_columns: Sequence[str] = (),
) -> list[dict[str, float]]:
    """Fit target-independent UID aggregates on one fold, then transform another."""

    amounts: dict[str, list[float]] = defaultdict(list)
    times: dict[str, list[float]] = defaultdict(list)
    values: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in fit_rows:
        key = uid_value(row, uid)
        amount = _number(row.get(amount_column))
        timestamp = _number(row.get(time_column))
        if amount is not None:
            amounts[key].append(amount)
        if timestamp is not None:
            times[key].append(timestamp)
        for column in aggregate_columns:
            value = _number(row.get(column))
            if value is not None:
                values[(key, column)].append(value)

    result = []
    for row in transform_rows:
        key = uid_value(row, uid)
        group_amounts = amounts.get(key, [])
        timestamp = _number(row.get(time_column))
        features = {
            "uid_count": float(len(group_amounts)),
            "uid_amount_mean": fmean(group_amounts) if group_amounts else 0.0,
            "uid_amount_std": pstdev(group_amounts) if len(group_amounts) > 1 else 0.0,
            "uid_frequency": len(group_amounts) / max(1, len(fit_rows)),
            "uid_time_delta": (timestamp - max(times[key]) if timestamp is not None and times.get(key) else 0.0),
        }
        for column in aggregate_columns:
            group = values.get((key, column), [])
            features[f"uid_{column}_mean"] = fmean(group) if group else 0.0
            features[f"uid_{column}_std"] = pstdev(group) if len(group) > 1 else 0.0
        result.append(features)
    return result


def client_slices(
    fit_uids: Sequence[Hashable],
    validation_uids: Sequence[Hashable],
) -> dict[str, list[int]]:
    counts = Counter(fit_uids)
    slices: dict[str, list[int]] = {"known": [], "new": [], "questionable": []}
    for index, value in enumerate(validation_uids):
        if counts[value] >= 2:
            slices["known"].append(index)
        elif counts[value] == 1:
            slices["questionable"].append(index)
        else:
            slices["new"].append(index)
    return slices


def client_frequency_slices(fit_uids: Sequence[Hashable], validation_uids: Sequence[Hashable]) -> dict[str, list[int]]:
    counts = Counter(fit_uids)
    result: dict[str, list[int]] = {"frequency_0": [], "frequency_1": [], "frequency_2_5": [], "frequency_6_plus": []}
    for index, uid in enumerate(validation_uids):
        count = counts[uid]
        if count == 0:
            key = "frequency_0"
        elif count == 1:
            key = "frequency_1"
        elif count <= 5:
            key = "frequency_2_5"
        else:
            key = "frequency_6_plus"
        result[key].append(index)
    return result


def client_slice_auc(
    targets: Sequence[int],
    predictions: Sequence[float],
    slices: Mapping[str, Sequence[int]],
) -> dict[str, float | None]:
    if len(targets) != len(predictions):
        raise ValueError("targets and predictions must align")
    result: dict[str, float | None] = {}
    for name, indices in slices.items():
        labels = [targets[index] for index in indices]
        scores = [predictions[index] for index in indices]
        result[f"{name}_client_auc"] = binary_auc(labels, scores) if len(set(labels)) == 2 else None
    return result


def client_level_average(predictions: Sequence[float], uids: Sequence[Hashable]) -> list[float]:
    if len(predictions) != len(uids):
        raise ValueError("predictions and uids must align")
    totals: dict[Hashable, list[float]] = defaultdict(list)
    for prediction, uid in zip(predictions, uids, strict=True):
        totals[uid].append(float(prediction))
    means = {uid: fmean(values) for uid, values in totals.items()}
    return [means[uid] for uid in uids]


def known_new_routing(
    global_predictions: Sequence[float],
    client_predictions: Sequence[float],
    known_indices: Sequence[int],
) -> list[float]:
    if len(global_predictions) != len(client_predictions):
        raise ValueError("routing predictions must align")
    known = set(known_indices)
    return [
        float(client_predictions[index] if index in known else global_predictions[index])
        for index in range(len(global_predictions))
    ]


def temporal_smoothing(
    predictions: Sequence[float],
    uids: Sequence[Hashable],
    *,
    strength: float = 0.25,
) -> list[float]:
    if not 0 <= strength <= 1 or len(predictions) != len(uids):
        raise ValueError("invalid smoothing strength or unaligned data")
    history: dict[Hashable, list[float]] = defaultdict(list)
    output = []
    for prediction, uid in zip(predictions, uids, strict=True):
        prior = fmean(history[uid]) if history[uid] else float(prediction)
        output.append((1 - strength) * float(prediction) + strength * prior)
        history[uid].append(float(prediction))
    return output


def histogram_calibration(
    fit_predictions: Sequence[float],
    fit_targets: Sequence[int],
    transform_predictions: Sequence[float],
    *,
    bins: int = 20,
) -> list[float]:
    """Fit calibration bins on one fold and transform another fold."""

    if len(fit_predictions) != len(fit_targets) or not fit_predictions or bins < 2:
        raise ValueError("calibration fit data must be aligned and bins >= 2")
    totals = [0] * bins
    positives = [0] * bins
    for prediction, target in zip(fit_predictions, fit_targets, strict=True):
        index = min(bins - 1, max(0, int(float(prediction) * bins)))
        totals[index] += 1
        positives[index] += int(target)
    rates = [positives[index] / totals[index] if totals[index] else (index + 0.5) / bins for index in range(bins)]
    return [rates[min(bins - 1, max(0, int(float(value) * bins)))] for value in transform_predictions]


def rank_blend(predictions: Mapping[str, Sequence[float]], weights: Mapping[str, float] | None = None) -> list[float]:
    if len(predictions) < 2 or len({len(values) for values in predictions.values()}) != 1:
        raise ValueError("rank blend requires at least two aligned candidates")
    identifiers = sorted(predictions)
    if weights is None:
        weights = {identifier: 1 / len(identifiers) for identifier in identifiers}
    if set(weights) != set(identifiers) or any(value < 0 for value in weights.values()):
        raise ValueError("rank blend weights must cover candidates and be non-negative")
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("rank blend weights must have positive mass")
    ranks = {identifier: _normalized_ranks(predictions[identifier]) for identifier in identifiers}
    width = len(next(iter(predictions.values())))
    return [sum(weights[item] / total * ranks[item][index] for item in identifiers) for index in range(width)]


def model_rank_stability(scores_by_horizon: Mapping[str, Sequence[float]]) -> float:
    """Mean Spearman correlation of model ranks between forward horizons."""

    if len(scores_by_horizon) < 2:
        raise ValueError("rank stability requires at least two model families")
    lengths = {len(scores) for scores in scores_by_horizon.values()}
    if len(lengths) != 1 or next(iter(lengths)) < 2:
        raise ValueError("rank stability requires at least two aligned horizons")
    models = sorted(scores_by_horizon)
    horizon_ranks = []
    for horizon in range(next(iter(lengths))):
        horizon_ranks.append(_normalized_ranks([scores_by_horizon[model][horizon] for model in models]))
    correlations = []
    for left, right in itertools.combinations(horizon_ranks, 2):
        left_mean = fmean(left)
        right_mean = fmean(right)
        numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right, strict=True))
        denominator = math.sqrt(
            sum((value - left_mean) ** 2 for value in left) * sum((value - right_mean) ** 2 for value in right)
        )
        correlations.append(numerator / denominator if denominator else 1.0)
    return fmean(correlations)


def make_model_family(name: str, *, seed: int = 42) -> Any:
    """Lazy solver-extra factory; orchestration remains free of ML dependencies."""

    if name == "logistic":
        from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]

        return LogisticRegression(max_iter=500, random_state=seed)
    if name == "lightgbm":
        from lightgbm import LGBMClassifier

        return LGBMClassifier(n_estimators=500, learning_rate=0.05, random_state=seed, verbosity=-1)
    raise ValueError(f"unsupported IEEE-CIS model family: {name}")


def require_adversarial_followup(*, adversarial_auc_changed: bool, forward_fraud_validation_completed: bool) -> None:
    if adversarial_auc_changed and not forward_fraud_validation_completed:
        raise ValueError(
            "adversarial AUC is diagnostic only; run multi-horizon forward fraud-label validation before adoption"
        )


def ieee_cis_capabilities() -> dict[str, object]:
    return {
        "uid_generation": True,
        "forward_horizons_minimum": 3,
        "time_gap": True,
        "fold_safe_uid_aggregation": True,
        "client_slices": ["known", "new", "questionable"],
        "model_families": ["lightgbm", "logistic"],
        "post_processing": ["client_average", "known_new_routing", "temporal_smoothing", "calibration"],
        "ensemble": ["weighted_blend", "rank_blend", "stack", "nested_cross_fit"],
        "oof_required": True,
    }


def binary_auc(targets: Sequence[int], predictions: Sequence[float]) -> float:
    if len(targets) != len(predictions) or not targets:
        raise ValueError("AUC requires aligned non-empty targets and predictions")
    positives = sum(targets)
    negatives = len(targets) - positives
    if positives == 0 or negatives == 0:
        raise ValueError("AUC requires both classes")
    ordered = sorted(enumerate(predictions), key=lambda item: item[1])
    ranks = [0.0] * len(predictions)
    cursor = 0
    while cursor < len(ordered):
        end = cursor + 1
        while end < len(ordered) and ordered[end][1] == ordered[cursor][1]:
            end += 1
        average_rank = (cursor + 1 + end) / 2
        for original, _ in ordered[cursor:end]:
            ranks[original] = average_rank
        cursor = end
    positive_rank_sum = sum(rank for rank, target in zip(ranks, targets, strict=True) if target == 1)
    return (positive_rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(result) else result


def _normalized_ranks(values: Sequence[float]) -> list[float]:
    if not values:
        raise ValueError("rank vector cannot be empty")
    ordered = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(ordered):
        end = cursor + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[cursor]]:
            end += 1
        average = (cursor + end - 1) / 2
        for index in ordered[cursor:end]:
            ranks[index] = average / max(1, len(values) - 1)
        cursor = end
    return ranks
