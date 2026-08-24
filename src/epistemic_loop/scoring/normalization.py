from __future__ import annotations


def higher_is_better(value: float, direction: str) -> float:
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
