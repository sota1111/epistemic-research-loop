from datetime import date


def published_before_competition(published_at: date | None, competition_started_at: date) -> bool:
    return published_at is not None and published_at < competition_started_at
