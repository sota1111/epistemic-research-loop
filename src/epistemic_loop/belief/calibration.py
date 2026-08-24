from __future__ import annotations


def brier_score(predictions: list[float], outcomes: list[bool]) -> float:
    if len(predictions) != len(outcomes) or not predictions:
        raise ValueError("predictions and outcomes must be equally sized and non-empty")
    return sum(
        (prediction - float(outcome)) ** 2 for prediction, outcome in zip(predictions, outcomes, strict=True)
    ) / len(predictions)
