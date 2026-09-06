"""Every configuration in `configs/` loads, and the ones that touch a real competition are safe.

A configuration that fails to parse is discovered at `erlctl init`, in front of a competition
deadline. A configuration that quietly permits an automatic submission is discovered later than
that.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from epistemic_loop.config import load_config

ROOT = Path(__file__).resolve().parents[2]
#: Full run configurations. `configs/benchmarks`, `configs/policies` and some of
#: `configs/verification` are fragments and profiles for other schemas, not `AppConfig` files.
CONFIGS = sorted([*(ROOT / "configs").glob("*.yaml"), *(ROOT / "configs" / "competitions").glob("*.yaml")])

PLACEHOLDERS = {
    "IEEE_CIS_AGENT_RUN_ID": "run-001",
    "IEEE_CIS_AGENT_SEED": "101",
    "IEEE_CIS_AGENT_WORKTREE": "/tmp/worktree",
    "NEDO_RUN_ID": "nedo-001",
    "NEDO_SEED": "101",
    "NEDO_REPO": "/tmp/nedo",
}


@pytest.fixture(autouse=True)
def _placeholders(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in PLACEHOLDERS.items():
        monkeypatch.setenv(name, os.environ.get(name, value))


@pytest.mark.parametrize("path", CONFIGS, ids=lambda path: str(path.relative_to(ROOT)))
def test_the_configuration_loads(path: Path) -> None:
    assert load_config(path) is not None


def test_no_shipped_configuration_carries_preferred_state_constants() -> None:
    """§3 item 8: a target without a cited source is the hand-written constant coming back."""
    for path in CONFIGS:
        config = load_config(path)
        if config.preferred_state.targets:
            assert config.preferred_state.source, f"{path} sets targets with no source"


def test_the_nedo_configuration_cannot_submit_on_its_own() -> None:
    """Real submissions are approved one at a time by a human (docs/handover.md), and the platform
    allows five a day -- exactly the budget a loop would spend without noticing."""
    config = load_config(ROOT / "configs" / "competitions" / "nedo_baggage_loading.yaml")

    assert config.budgets.max_final_submissions == 0
    assert config.budgets.max_daily_submissions == 0
    assert config.leaderboard.max_public_queries == 0
    assert config.holdout.policy.value == "strict_blind"
    assert config.executor.adapter == "competition_repo"
