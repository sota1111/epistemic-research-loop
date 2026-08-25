from __future__ import annotations


def higher_is_better(value: float, direction: str) -> float:
    """Re-express an observed metric so that larger is better, whichever way the metric runs.

    Anything that ranks raw observations has to go through this. Without it a report written for a
    maximised metric silently reports the *worst* result as the best one the moment it is pointed
    at a minimised competition, and nothing about the output looks wrong.
    """
    if direction == "maximize":
        return value
    if direction == "minimize":
        return -value
    raise ValueError(f"unknown metric direction: {direction}")


def min_max(values: list[float]) -> list[float]:
    if not values:
        return []
    low, high = min(values), max(values)
    if high == low:
        return [0.5 for _ in values]
    return [(value - low) / (high - low) for value in values]
