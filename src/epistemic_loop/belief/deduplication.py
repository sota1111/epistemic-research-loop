from __future__ import annotations

import re

from epistemic_loop.domain.models import Hypothesis


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]+", text.lower()))


def claim_similarity(left: str, right: str) -> float:
    left_tokens, right_tokens = _tokens(left), _tokens(right)
    union = left_tokens | right_tokens
    return len(left_tokens & right_tokens) / len(union) if union else 1.0


def find_merge_candidate(
    candidate: Hypothesis,
    existing: list[Hypothesis],
    threshold: float = 0.8,
) -> Hypothesis | None:
    matches = [
        hypothesis
        for hypothesis in existing
        if hypothesis.type == candidate.type and claim_similarity(hypothesis.claim, candidate.claim) >= threshold
    ]
    return max(matches, key=lambda item: claim_similarity(item.claim, candidate.claim), default=None)
