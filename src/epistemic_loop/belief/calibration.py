from __future__ import annotations

import math
from collections.abc import Iterable

from epistemic_loop.domain.models import CalibrationSummary, ForecastCalibrationRecord


def brier_score(predictions: list[float], outcomes: list[bool]) -> float:
    if len(predictions) != len(outcomes) or not predictions:
        raise ValueError("predictions and outcomes must be equally sized and non-empty")
    return sum(
        (prediction - float(outcome)) ** 2 for prediction, outcome in zip(predictions, outcomes, strict=True)
    ) / len(predictions)


def summarize_calibration(records: Iterable[ForecastCalibrationRecord]) -> CalibrationSummary:
    values = list(records)
    if not values:
        raise ValueError("calibration requires at least one forecast record")
    brier = 0.0
    log_loss = 0.0
    correct = 0
    confidences: list[float] = []
    overconfident = underconfident = 0
    coverages: dict[str, list[bool]] = {"0.5": [], "0.8": [], "0.95": []}
    for record in values:
        top_label, confidence = max(record.probabilities.items(), key=lambda item: (item[1], item[0]))
        hit = top_label == record.observed_label
        correct += int(hit)
        confidences.append(confidence)
        overconfident += int(not hit and confidence >= 0.5)
        underconfident += int(hit and confidence < 0.5)
        brier += sum(
            (probability - float(label == record.observed_label)) ** 2
            for label, probability in record.probabilities.items()
        ) / len(record.probabilities)
        log_loss -= math.log(max(record.probabilities[record.observed_label], 1e-12))
        for level, covered in record.interval_coverage.items():
            if level in coverages:
                coverages[level].append(covered)
    count = len(values)
    return CalibrationSummary(
        count=count,
        brier_score=brier / count,
        log_loss=log_loss / count,
        accuracy=correct / count,
        mean_confidence=sum(confidences) / count,
        overconfidence_rate=overconfident / count,
        underconfidence_rate=underconfident / count,
        interval_coverage_50=_mean_bool(coverages["0.5"]),
        interval_coverage_80=_mean_bool(coverages["0.8"]),
        interval_coverage_95=_mean_bool(coverages["0.95"]),
    )


def _mean_bool(values: list[bool]) -> float | None:
    return sum(values) / len(values) if values else None
