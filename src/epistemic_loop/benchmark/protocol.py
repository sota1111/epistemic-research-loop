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
    systems: tuple[str, str] = ("exploiter_only", "epistemic")
    source_policy: str = "strict_historical"
    holdout_policy: str = "strict_blind"
    max_final_submissions: int = 1


def save_plan(plan: BenchmarkPlan, path: str | Path) -> None:
    Path(path).write_text(yaml.safe_dump(plan.model_dump(mode="json"), sort_keys=False), encoding="utf-8")


def load_plan(path: str | Path) -> BenchmarkPlan:
    return BenchmarkPlan.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))
