from __future__ import annotations

from enum import StrEnum
from urllib.parse import urlparse


class UrlClass(StrEnum):
    KAGGLE_DISCUSSION = "kaggle_discussion"
    KAGGLE_CODE = "kaggle_code"
    KAGGLE_COMPETITION = "kaggle_competition"
    GITHUB = "github"
    PAPER = "paper"
    OFFICIAL_DOCS = "official_docs"
    OTHER = "other"


def classify_url(url: str) -> UrlClass:
    parsed = urlparse(url)
    host = parsed.hostname.lower() if parsed.hostname else ""
    path = parsed.path.lower()
    if host.endswith("kaggle.com"):
        if "/discussion" in path or "/topics" in path:
            return UrlClass.KAGGLE_DISCUSSION
        if "/code" in path or "/notebooks" in path:
            return UrlClass.KAGGLE_CODE
        if "/competitions/" in path:
            return UrlClass.KAGGLE_COMPETITION
    if host in {"github.com", "www.github.com"}:
        return UrlClass.GITHUB
    if host in {"arxiv.org", "openreview.net", "doi.org"}:
        return UrlClass.PAPER
    if host.endswith(("readthedocs.io", "scikit-learn.org", "pytorch.org")):
        return UrlClass.OFFICIAL_DOCS
    return UrlClass.OTHER
