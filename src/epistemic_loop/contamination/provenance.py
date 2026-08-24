from __future__ import annotations

import hashlib
from datetime import date
from typing import Literal

from epistemic_loop.domain.models import SourceRef


def source_ref(
    *,
    identifier: str,
    title: str,
    source_type: Literal["paper", "official_docs", "competition_page", "other"],
    content: bytes,
    allowed: bool,
    reason: str,
    url: str | None = None,
    published_at: date | None = None,
    competition_specific: bool = False,
) -> SourceRef:
    return SourceRef(
        id=identifier,
        title=title,
        source_type=source_type,
        published_at=published_at,
        competition_specific=competition_specific,
        allowed=allowed,
        policy_reason=reason,
        content_hash=hashlib.sha256(content).hexdigest(),
        url=url,
    )
