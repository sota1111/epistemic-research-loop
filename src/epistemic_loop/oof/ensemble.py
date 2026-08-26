from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence

from epistemic_loop.domain.models import OOFEnsemble, OOFRecord


def build_cross_fitted_ensemble(
    records: Iterable[OOFRecord],
    *,
    run_id: str,
    ensemble_id: str,
    iterations: int = 400,
    learning_rate: float = 0.2,
    artifact_ids: Sequence[str] = (),
) -> OOFEnsemble:
    """Fit simplex weights off-fold and evaluate each row with weights that never saw it."""

    grouped: dict[str, dict[tuple[str, str], OOFRecord]] = defaultdict(dict)
    for record in records:
        key = (record.validation_world, record.row_id)
        if key in grouped[record.candidate_id]:
            raise ValueError(f"duplicate OOF row identity for {record.candidate_id}: {key}")
        grouped[record.candidate_id][key] = record
    candidate_ids = sorted(grouped)
    if len(candidate_ids) < 2:
        raise ValueError("an OOF ensemble requires at least two candidates")
    reference = grouped[candidate_ids[0]]
    keys = sorted(reference)
    if not keys or any(set(grouped[item]) != set(reference) for item in candidate_ids):
        raise ValueError("ensemble candidates must cover identical OOF rows")
    worlds = {key[0] for key in keys}
    if len(worlds) != 1:
        raise ValueError("build one cross-fitted ensemble per validation world")
    folds = sorted({reference[key].fold_id for key in keys})
    if len(folds) < 2:
        raise ValueError("cross-fitted ensemble needs at least two folds")
    for key in keys:
        expected_target = reference[key].target
        expected_fold = reference[key].fold_id
        if any(
            grouped[candidate_id][key].target != expected_target or grouped[candidate_id][key].fold_id != expected_fold
            for candidate_id in candidate_ids
        ):
            raise ValueError(f"target or fold mismatch for OOF row {key}")

    fold_weights: dict[str, dict[str, float]] = {}
    squared_error = 0.0
    best_single_error = [0.0] * len(candidate_ids)
    evaluated = 0
    for fold in folds:
        train_keys = [key for key in keys if reference[key].fold_id != fold]
        valid_keys = [key for key in keys if reference[key].fold_id == fold]
        matrix = [[grouped[item][key].oof_prediction for item in candidate_ids] for key in train_keys]
        targets = [reference[key].target for key in train_keys]
        weights = _fit_simplex_weights(matrix, targets, iterations=iterations, learning_rate=learning_rate)
        fold_weights[fold] = dict(zip(candidate_ids, weights, strict=True))
        for key in valid_keys:
            predictions = [grouped[item][key].oof_prediction for item in candidate_ids]
            target = reference[key].target
            blended = sum(weight * prediction for weight, prediction in zip(weights, predictions, strict=True))
            squared_error += (target - blended) ** 2
            for index, prediction in enumerate(predictions):
                best_single_error[index] += (target - prediction) ** 2
            evaluated += 1
    if not evaluated:
        raise ValueError("cross-fitted ensemble has no validation rows")
    averaged = [sum(fold_weights[fold][item] for fold in folds) / len(folds) for item in candidate_ids]
    final_weights = _project_simplex(averaged)
    ensemble_loss = squared_error / evaluated
    best_loss = min(value / evaluated for value in best_single_error)
    return OOFEnsemble(
        id=ensemble_id,
        run_id=run_id,
        candidate_ids=candidate_ids,
        validation_world=next(iter(worlds)),
        weights=dict(zip(candidate_ids, final_weights, strict=True)),
        fold_weights=fold_weights,
        cross_fitted_loss=ensemble_loss,
        best_single_loss=best_loss,
        marginal_gain=best_loss - ensemble_loss,
        artifact_ids=list(artifact_ids),
    )


def blend_predictions(predictions: Mapping[str, Sequence[float]], weights: Mapping[str, float]) -> list[float]:
    if set(predictions) != set(weights) or not predictions:
        raise ValueError("prediction vectors and weights must cover the same candidates")
    lengths = {len(values) for values in predictions.values()}
    if len(lengths) != 1:
        raise ValueError("prediction vectors must have equal length")
    candidate_ids = sorted(weights)
    return [
        sum(weights[item] * predictions[item][index] for item in candidate_ids) for index in range(next(iter(lengths)))
    ]


def _fit_simplex_weights(
    matrix: Sequence[Sequence[float]],
    targets: Sequence[float],
    *,
    iterations: int,
    learning_rate: float,
) -> list[float]:
    if len(matrix) != len(targets) or not matrix:
        raise ValueError("weight fitting requires aligned non-empty rows and targets")
    width = len(matrix[0])
    if width < 2 or any(len(row) != width for row in matrix):
        raise ValueError("prediction matrix must have a stable width of at least two")
    if iterations < 1 or learning_rate <= 0:
        raise ValueError("iterations and learning_rate must be positive")
    weights = [1 / width] * width
    for _ in range(iterations):
        gradient = [0.0] * width
        for row, target in zip(matrix, targets, strict=True):
            error = sum(weight * value for weight, value in zip(weights, row, strict=True)) - target
            for index, value in enumerate(row):
                gradient[index] += 2 * error * value / len(matrix)
        weights = _project_simplex(
            [weight - learning_rate * derivative for weight, derivative in zip(weights, gradient, strict=True)]
        )
    return weights


def _project_simplex(values: Sequence[float]) -> list[float]:
    """Euclidean projection onto non-negative weights summing to one."""

    ordered = sorted(values, reverse=True)
    cumulative = 0.0
    rho = 0
    for index, value in enumerate(ordered, start=1):
        cumulative += value
        if value - (cumulative - 1) / index > 0:
            rho = index
    if rho == 0:
        return [1 / len(values)] * len(values)
    threshold = (sum(ordered[:rho]) - 1) / rho
    projected = [max(value - threshold, 0.0) for value in values]
    total = sum(projected)
    return [value / total for value in projected]
