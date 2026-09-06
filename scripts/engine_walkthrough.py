#!/usr/bin/env python3
"""Drive one run end to end through `erlctl`, exactly as the README documents it.

`docs/v050_course_correction.md` §1.1: the engine has never been used in a real campaign. The only
campaign rebuilt population, evolution, crossover and selection on the spot, and the 61 enforced
capabilities have no operating record at all. That is item 1 and it needs a real competition.

This script is not that. It is the smaller thing that had never been checked either: **that the
documented command sequence actually runs**. Every step here is a separate `erlctl` process against
a scratch home -- init, start, hypothesis request/record, experiment request/propose/select,
dispatch, import, falsify, belief update, phase advance, report -- so nothing is exercised
in-process that a real operator would reach through the CLI.

    uv run python scripts/engine_walkthrough.py --home /tmp/erl-walkthrough

What it establishes: the loop can be driven from the shell without bypassing it, and the run leaves
an event log a report can be built from. What it does not establish: anything about a competition.
The worker is a stub that writes fixed metrics.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RUN = "walkthrough-001"

CONFIG = """\
run:
  id: null
  mode: system_c
  seed: 101
competition:
  slug: local-walkthrough
  metric_direction: maximize
  primary_metric: score
  data_path: data
executor:
  adapter: local
  workspace: .
  result_root: .results
artifacts:
  adapter: local
  root: .runs
storage:
  event_store: jsonl
  projection: sqlite
  sqlite_path: .state/epistemic-loop.db
holdout:
  policy: strict_blind
"""

WORKER = """\
import json, os, pathlib

output = pathlib.Path(os.environ["ERL_OUTPUT_DIR"])
output.mkdir(parents=True, exist_ok=True)
output.joinpath("metrics.json").write_text(json.dumps({"auc_gap": 0.061, "score": 0.71}))
output.joinpath("fold_metrics.json").write_text(json.dumps({"folds": [0.05, 0.06]}))
"""


def _hypotheses() -> list[dict[str, Any]]:
    """Two, not one. System C refuses to compute information gain for a hypothesis with no named
    alternative: a likelihood ratio against nothing is not a discrimination."""
    primary = _hypothesis()
    alternative = {
        **primary,
        "id": "H-002",
        "type": "leakage",
        "claim": "the gap comes from fold size, not from time order",
        "rationale": "the temporal folds are smaller than the random ones",
        "alternative_hypothesis_ids": ["H-001"],
    }
    primary["alternative_hypothesis_ids"] = ["H-002"]
    return [primary, alternative]


def _hypothesis() -> dict[str, Any]:
    prediction = {
        "description": "temporal CV score is lower than random CV",
        "metric_name": "auc_gap",
        "expected_direction": "increase",
        "expected_range": {"min": 0.02, "max": 0.20},
        "condition": "same features and model",
        "discriminates_from": ["H-GROUP"],
    }
    return {
        "id": "H-001",
        "run_id": RUN,
        "type": "temporal_structure",
        "claim": "time shift makes random CV optimistic",
        "rationale": "a time column is present",
        "scope": "validation",
        "prior_confidence": 0.5,
        "current_confidence": 0.5,
        "predictions_if_true": [prediction],
        "predictions_if_false": [
            {**prediction, "description": "temporal and random CV agree", "expected_direction": "unchanged"}
        ],
        "falsification_requirements": ["random vs temporal split"],
        "downstream_consequence": "critical",
        "created_by": "walkthrough",
        "prompt_version": "v1",
    }


def _experiment(home: Path) -> dict[str, Any]:
    prediction = _hypothesis()["predictions_if_true"][0]
    return {
        "id": "EXP-001",
        "run_id": RUN,
        "experiment_type": "diagnostic",
        "hypothesis_ids": ["H-001"],
        "research_question": "Does temporal CV expose shift?",
        "protocol": "Run the same baseline on random and out-of-time splits",
        "controls": ["same features", "same model"],
        "split_strategy": "random_vs_temporal",
        "seeds": [11, 23],
        "metrics": ["auc_gap"],
        "predicted_outcomes": [prediction],
        # System C refuses an epistemic experiment without preregistered likelihoods: the
        # information gain is computed from these and the belief, never from a self-score.
        "outcome_forecasts": [
            {
                "hypothesis_id": "H-001",
                "outcomes": [
                    {"label": "gap>=0.02", "probability_if_true": 0.8, "probability_if_false": 0.2},
                    {"label": "gap<0.02", "probability_if_true": 0.2, "probability_if_false": 0.8},
                ],
                "decisions_affected": ["which split the run steers by"],
                "measurement_notes": "auc_gap from one baseline under both splits, two seeds",
            }
        ],
        "decision_rule": "support H-001 when temporal gap >= 0.02 in both seeds",
        "expected_score_gain": {"mean_gain": 0.05, "uncertainty": 0.01},
        "epistemic_assessment": {
            "hypothesis_discrimination": 4,
            "uncertainty_reduction": 4,
            "decision_consequence": 4,
            "search_space_reduction": 3,
            "outcome_observability": 4,
            "rationale": "direct split comparison",
        },
        "robustness_assessment": {
            "seed_coverage": 1,
            "fold_coverage": 1,
            "subgroup_coverage": 0.5,
            "temporal_coverage": 1,
            "leakage_checks": 0.5,
            "rationale": "two seeds and both split types",
        },
        "novelty_score": 0.9,
        "estimated_cost": {"cpu_hours": 1, "wall_hours": 0.5},
        "implementation_request": {"command": f"python3 {home / 'worker' / 'run.py'}"},
        "required_artifacts": ["metrics.json", "fold_metrics.json"],
        "lineage": "validation",
    }


def _verdict() -> dict[str, Any]:
    return {
        "hypothesis_id": "H-001",
        "observation_ids": [],
        "supporting_predictions": ["auc_gap 0.061 exceeds the 0.02 threshold under both seeds"],
        "contradicting_predictions": [],
        "alternative_explanation": "the gap could come from fold size rather than time order",
        "confounders_checked": ["fold size", "feature set"],
        "recommended_next_test": "repeat with matched fold sizes",
    }


class Walkthrough:
    def __init__(self, home: Path, command: list[str]) -> None:
        self.home = home
        self.command = command
        self.transcript: list[dict[str, Any]] = []

    def run(self, *arguments: str) -> dict[str, Any]:
        environment = {**os.environ, "ERL_HOME": str(self.home), "ERL_PROMPTS_ROOT": str(ROOT / "prompts")}
        completed = subprocess.run(
            [*self.command, *arguments],
            cwd=self.home,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        step = {
            "command": f"erlctl {' '.join(arguments)}",
            "exit_code": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip()[-2000:],
        }
        self.transcript.append(step)
        if completed.returncode != 0:
            raise SystemExit(f"step failed: {step['command']}\n{completed.stdout}\n{completed.stderr}")
        return step


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, required=True, help="scratch directory for the run")
    parser.add_argument(
        "--erlctl",
        default="",
        help="how to invoke the CLI; defaults to `erlctl` on PATH, else this interpreter's module",
    )
    parser.add_argument("--transcript", type=Path, help="write the step-by-step transcript here")
    parser.add_argument("--keep", action="store_true", help="do not clear an existing home first")
    arguments = parser.parse_args()

    home: Path = arguments.home.resolve()
    if home.exists() and not arguments.keep:
        shutil.rmtree(home)
    (home / "data").mkdir(parents=True, exist_ok=True)
    (home / "worker").mkdir(parents=True, exist_ok=True)
    (home / "erl.yaml").write_text(CONFIG, encoding="utf-8")
    (home / "data" / "train.csv").write_text("id,feature,target\n1,0.4,0\n2,0.9,1\n", encoding="utf-8")
    (home / "worker" / "run.py").write_text(WORKER, encoding="utf-8")
    (home / "hypotheses.json").write_text(json.dumps({"hypotheses": _hypotheses()}, indent=2), encoding="utf-8")
    (home / "experiments.json").write_text(json.dumps({"experiments": [_experiment(home)]}, indent=2), encoding="utf-8")

    command = (
        shlex.split(arguments.erlctl)
        if arguments.erlctl
        else ([executable] if (executable := shutil.which("erlctl")) else [sys.executable, "-m", "epistemic_loop"])
    )
    walkthrough = Walkthrough(home, command)
    walkthrough.run("init", "--competition", "local-walkthrough", "--config", "erl.yaml", "--run-id", RUN)
    walkthrough.run("run", "start", "--run-id", RUN)
    walkthrough.run("hypotheses", "request", "--run-id", RUN)
    walkthrough.run("hypotheses", "record", "--run-id", RUN, "--from", "hypotheses.json")
    walkthrough.run("experiments", "request", "--run-id", RUN)
    walkthrough.run("experiments", "propose", "--run-id", RUN, "--from", "experiments.json")
    selection = json.loads(walkthrough.run("experiments", "select", "--run-id", RUN, "--size", "1")["stdout"])
    if selection["selected_experiment_ids"] != ["EXP-001"]:
        raise SystemExit(f"selection refused the only candidate: {selection['rejected_reasons']}")
    walkthrough.run("experiments", "dispatch", "--run-id", RUN, "--experiment-id", "EXP-001")
    imported = json.loads(
        walkthrough.run("experiments", "import-result", "--run-id", RUN, "--experiment-id", "EXP-001")["stdout"]
    )

    verdict = _verdict()
    verdict["observation_ids"] = [imported["observation_id"]]
    (home / "verdict.json").write_text(json.dumps(verdict, indent=2), encoding="utf-8")
    walkthrough.run("beliefs", "update", "--run-id", RUN, "--from", "verdict.json")
    walkthrough.run("run", "advance", "--run-id", RUN)
    status = json.loads(walkthrough.run("run", "status", "--run-id", RUN)["stdout"])
    report = walkthrough.run("report", "run", "--run-id", RUN)["stdout"]
    walkthrough.run("run", "replay", "--run-id", RUN)

    summary = {
        "home": str(home),
        "run_id": RUN,
        "steps": len(walkthrough.transcript),
        "events": status["event_count"],
        "observations": status["observations"],
        "hypotheses": status["hypotheses"],
        "phase": status["phase"],
        "report": report,
        "report_bytes": Path(report).stat().st_size,
    }
    if arguments.transcript:
        arguments.transcript.write_text(
            json.dumps({"summary": summary, "steps": walkthrough.transcript}, indent=2) + "\n",
            encoding="utf-8",
        )
    json.dump(summary, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
