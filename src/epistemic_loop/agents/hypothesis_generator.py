from __future__ import annotations

from typing import Protocol

from epistemic_loop.domain.models import CompetitionWorldModel, Hypothesis


class HypothesisGenerator(Protocol):
    def generate(self, run_id: str, world_model: CompetitionWorldModel) -> list[Hypothesis]: ...


def validate_generated_hypotheses(hypotheses: list[Hypothesis], maximum: int = 30) -> None:
    if len(hypotheses) > maximum:
        raise ValueError(f"generator returned {len(hypotheses)} hypotheses; maximum is {maximum}")
    identifiers = [item.id for item in hypotheses]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("generator returned duplicate hypothesis identifiers")
