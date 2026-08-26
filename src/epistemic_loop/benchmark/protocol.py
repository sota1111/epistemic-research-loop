from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class BenchmarkPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    benchmark_id: str
    scenarios: list[str]
    replicates: int = Field(ge=3)
    seeds: list[int]
    budgets: dict[str, float | int]
    systems: tuple[str, ...] = Field(default=("exploiter_only", "epistemic"), min_length=2)
    source_policy: str = "strict_historical"
    holdout_policy: str = "strict_blind"
    max_final_submissions: int = 1

    def model_post_init(self, __context: object) -> None:
        if len(self.systems) != len(set(self.systems)):
            raise ValueError("benchmark systems must be unique")
        if len(self.seeds) < self.replicates:
            raise ValueError("benchmark needs at least one seed per replicate")


def save_plan(plan: BenchmarkPlan, path: str | Path) -> None:
    Path(path).write_text(yaml.safe_dump(plan.model_dump(mode="json"), sort_keys=False), encoding="utf-8")


def load_plan(path: str | Path) -> BenchmarkPlan:
    return BenchmarkPlan.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))
