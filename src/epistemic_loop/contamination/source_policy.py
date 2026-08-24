from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from epistemic_loop.contamination.date_filter import published_before_competition
from epistemic_loop.contamination.url_classifier import UrlClass, classify_url


@dataclass(frozen=True)
class SourceDecision:
    allowed: bool
    reason: str


class StrictHistoricalSourcePolicy:
    def __init__(self, competition_slug: str, competition_started_at: date):
        self.competition_slug = competition_slug.lower()
        self.competition_started_at = competition_started_at
        self.slug_tokens = set(re.findall(r"[a-z0-9]+", self.competition_slug))

    def evaluate(
        self,
        url: str,
        *,
        title: str,
        published_at: date | None,
        competition_specific: bool,
    ) -> SourceDecision:
        category = classify_url(url)
        if category in {UrlClass.KAGGLE_DISCUSSION, UrlClass.KAGGLE_CODE}:
            return SourceDecision(False, f"{category.value} is prohibited in strict historical mode")
        if category == UrlClass.GITHUB and competition_specific:
            return SourceDecision(False, "competition-specific GitHub repositories are prohibited")
        if competition_specific and category != UrlClass.KAGGLE_COMPETITION:
            return SourceDecision(False, "competition-specific solution material is prohibited")
        if category == UrlClass.KAGGLE_COMPETITION:
            return SourceDecision(True, "official competition page is allowed")
        if category in {UrlClass.PAPER, UrlClass.OFFICIAL_DOCS}:
            if published_at is None:
                return SourceDecision(False, "publication date is required")
            if not published_before_competition(published_at, self.competition_started_at):
                return SourceDecision(False, "source was not published before the competition")
            return SourceDecision(True, "general pre-competition material is allowed")
        title_tokens = set(re.findall(r"[a-z0-9]+", title.lower()))
        if len(self.slug_tokens & title_tokens) >= max(2, len(self.slug_tokens) // 2):
            return SourceDecision(False, "title appears competition-specific")
        return SourceDecision(False, "unclassified sources require explicit provenance review")

    def validate_search_query(self, query: str) -> SourceDecision:
        query_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
        if len(self.slug_tokens & query_tokens) >= max(2, len(self.slug_tokens) // 2):
            return SourceDecision(False, "competition slug must not be sent to the literature search")
        return SourceDecision(True, "generic domain query")
