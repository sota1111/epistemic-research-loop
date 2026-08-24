from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GoldFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    category: str
    concept: str
    acceptable_discovery_patterns: list[str] = Field(min_length=1)
    weight: int = Field(default=1, ge=1)


def concept_match(text: str, finding: GoldFinding) -> bool:
    normalized = text.casefold()
    return any(pattern.casefold() in normalized for pattern in finding.acceptable_discovery_patterns)
