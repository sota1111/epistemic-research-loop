from __future__ import annotations


def parse_optional_score(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid score: {value!r}") from error


def percentile(score: float, leaderboard_scores: list[float], direction: str) -> float:
    if not leaderboard_scores:
        raise ValueError("leaderboard scores are empty")
    if direction == "maximize":
        outranked = sum(value > score for value in leaderboard_scores)
    elif direction == "minimize":
        outranked = sum(value < score for value in leaderboard_scores)
    else:
        raise ValueError(f"unknown metric direction: {direction}")
    return 1.0 - outranked / len(leaderboard_scores)
