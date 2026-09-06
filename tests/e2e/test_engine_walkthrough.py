"""The documented `erlctl` sequence runs, end to end, as a sequence of real processes.

`docs/v050_course_correction.md` §1.1 -- the engine has no operating record at all, and the README's
command list had never been executed as a list. This is not item 1 (that needs a competition); it is
the check that the loop can be driven from the shell without bypassing it, which item 1 assumes.

Everything here goes through `scripts/engine_walkthrough.py`, which spawns one CLI process per step.
Nothing is exercised in-process that an operator would reach through the CLI.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "engine_walkthrough.py"


@pytest.fixture(scope="module")
def walkthrough(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    home = tmp_path_factory.mktemp("walkthrough-home")
    transcript = home.parent / "transcript.json"
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--home", str(home), "--transcript", str(transcript), "--keep"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return json.loads(transcript.read_text(encoding="utf-8"))


def test_every_documented_step_exits_zero(walkthrough: dict[str, object]) -> None:
    steps = walkthrough["steps"]
    assert isinstance(steps, list)

    commands = [step["command"] for step in steps]

    assert [step["exit_code"] for step in steps] == [0] * len(steps)
    # The sequence the README documents, in order, each one its own process.
    assert commands[0].startswith("erlctl init")
    for fragment in (
        "run start",
        "hypotheses request",
        "hypotheses record",
        "experiments request",
        "experiments propose",
        "experiments select",
        "experiments dispatch",
        "experiments import-result",
        "beliefs update",
        "run advance",
        "report run",
        "run replay",
    ):
        assert any(fragment in command for command in commands), fragment


def test_the_run_leaves_an_event_log_a_report_is_built_from(walkthrough: dict[str, object]) -> None:
    summary = walkthrough["summary"]
    assert isinstance(summary, dict)

    assert summary["events"] > 0
    assert summary["observations"] == 1
    assert summary["report_bytes"] > 0
    assert Path(str(summary["report"])).is_file()


def test_the_log_replays_to_the_same_event_count(walkthrough: dict[str, object]) -> None:
    steps = walkthrough["steps"]
    assert isinstance(steps, list)
    summary = walkthrough["summary"]
    assert isinstance(summary, dict)

    replay = json.loads(next(step["stdout"] for step in steps if "run replay" in step["command"]))

    assert replay["replayed_events"] == summary["events"]


def test_selection_took_the_candidate_rather_than_refusing_it(walkthrough: dict[str, object]) -> None:
    """The two refusals this walkthrough had to satisfy first are the engine working, not failing:
    System C will not score an epistemic experiment without preregistered likelihoods, and will not
    compute information gain for a hypothesis with no named alternative."""
    steps = walkthrough["steps"]
    assert isinstance(steps, list)

    decision = json.loads(next(step["stdout"] for step in steps if "experiments select" in step["command"]))

    assert decision["selected_experiment_ids"] == ["EXP-001"]
    assert decision["rejected_reasons"] == {}
