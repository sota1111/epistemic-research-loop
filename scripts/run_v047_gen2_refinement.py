#!/usr/bin/env python3
"""Run one v0.4.7 generation-2 "evolution" refinement, building on a completed run.

Reuses the parent run_id's EXISTING workdir (same suite_id/run_id, same column salt, same
saved scripts/pickles/agent_submission.json/final_predictions.csv left over from
generation 1) rather than a fresh view -- the whole point is that this agent's own prior
code already applies unchanged (docs/c_lite_v047_policy.md SS2.2). Backs up the generation-1
outputs before re-invoking so both are preserved for comparison. Only overwrites
final_predictions.csv/agent_submission.json if the refined attempt still validates; the
prompt instructs the agent not to regress, but this script does not itself compare scores
-- that judgment (and whether "improved" claims hold up) is made when the results are
reviewed, matching this project's standing practice of never trusting a single self-report.

CLI dispatch (_command/CLAUDE_SETTINGS/_environment) is deliberately duplicated from
run_v047_agent.py rather than imported -- scripts/ is not a package, and importlib-loading
a sibling script at runtime for production logic is worse than a small, self-contained
duplication (same rationale as scripts/v044_score_confirmation.py's docstring).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from collections.abc import Mapping
from pathlib import Path

from epistemic_loop.benchmark.v047_kaggle_submission_suite import V047_CANDIDATE_CONFIGS

#: Same text as run_v047_agent.py's RUNNER_INSTRUCTIONS (duplicated for the same reason as
#: _command/CLAUDE_SETTINGS below). Rewritten into the parent workdir before every gen2
#: invocation, since generation-1 workdirs were written before the "never inspect your own
#: process environment" rule was added (docs/verification/v047_env_var_blindness_incident.md)
#: and would otherwise still carry the old text.
RUNNER_INSTRUCTIONS = """# Operational rules for this research run

- Work ONLY inside this directory. Never read, list, or write files outside it. Never use the
  network, except for invoking `./score_confirmation.py` (a local, offline tool -- not
  internet access).
- Never run `env`, `printenv`, `set`, or otherwise inspect your own process environment
  variables. This directory's tools need certain environment variables to function, but
  their values are not yours to read or report -- treat your process environment the same
  as the filesystem outside this directory.
- `agent_prompt.md` is the binding research prompt. `agent_packet.json` describes the data
  files and the scoring tool's exact invocation command.
- Write your final output to `agent_submission.json` in this directory, and your
  real_test.csv predictions to `final_predictions.csv` (row_id,prediction; do not embed
  these in agent_submission.json -- there are far too many).
- python3 is available. Keep your analysis code in this directory.
"""

REFINEMENT_KICKOFF = (
    "You are continuing a research task in this SAME directory -- your own prior work is "
    "already here. Read agent_submission.json (your own approach_summary and confirmation "
    "results from your first pass) and inspect the scripts/models you already left behind. "
    "Your goal now: deliberately try to find a genuinely better approach than the one you "
    "already submitted -- new features, different model families, a more careful attack on "
    "your own current best approach, better ensembling, whatever you judge promising. Use "
    "./score_confirmation.py again if useful (it remembers your prior call count). "
    "If, and only if, you find something that beats your prior confirmation score, overwrite "
    "agent_submission.json and final_predictions.csv with the improved approach and explain "
    "in approach_summary exactly what changed and why you believe it is better. If you do NOT "
    "find an improvement, say so explicitly in approach_summary and leave "
    "agent_submission.json and final_predictions.csv exactly as they were -- do not regress."
)

CLAUDE_SETTINGS = {
    "permissions": {
        "deny": [
            "Read(//workspaces/**)",
            "Glob(//workspaces/**)",
            "Grep(//workspaces/**)",
            "Read(//home/*/.erl-controller/**)",
            "WebFetch",
            "WebSearch",
            "Bash(curl:*)",
            "Bash(wget:*)",
            "Bash(git:*)",
        ]
    }
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-id", required=True)
    parser.add_argument("--run-id", required=True, help="the parent (generation-1) run_id to build on")
    parser.add_argument("--output-root", type=Path, default=Path(".runs/v047/agent_outputs"))
    parser.add_argument("--truth-root", type=Path, default=Path(".controller_truth/v047"))
    parser.add_argument("--scorer-key-file", type=Path, default=Path(".state/v044/scorer.key"))
    parser.add_argument("--workdir-root", type=Path, default=Path.home() / "erl-v047-runs")
    parser.add_argument("--timeout-seconds", type=float, default=10800)
    arguments = parser.parse_args()
    if arguments.run_id not in V047_CANDIDATE_CONFIGS:
        raise SystemExit(f"run id {arguments.run_id!r} has no preregistered v0.4.7 execution configuration")
    config = V047_CANDIDATE_CONFIGS[arguments.run_id]

    workdir = arguments.workdir_root / arguments.suite_id / arguments.run_id
    submission_path = workdir / "agent_submission.json"
    final_predictions_path = workdir / "final_predictions.csv"
    if not submission_path.exists() or not final_predictions_path.exists():
        raise SystemExit(f"parent run {arguments.suite_id}/{arguments.run_id} has no completed generation-1 output")

    output_dir = arguments.output_root / arguments.suite_id / arguments.run_id / "gen2"
    if (output_dir / "agent_submission.json").exists():
        raise SystemExit(f"gen2 output already recorded for {arguments.suite_id}/{arguments.run_id}")
    output_dir.mkdir(parents=True, exist_ok=True)

    gen1_submission_backup = workdir / "agent_submission_gen1.json"
    gen1_predictions_backup = workdir / "final_predictions_gen1.csv"
    if not gen1_submission_backup.exists():
        shutil.copy2(submission_path, gen1_submission_backup)
    if not gen1_predictions_backup.exists():
        shutil.copy2(final_predictions_path, gen1_predictions_backup)

    # Refresh RUNNER.md with the current instructions (in particular the "never inspect your
    # own process environment" rule added after docs/verification/v047_env_var_blindness_incident.md)
    # -- generation-1 workdirs were written before that fix and would otherwise carry the old text.
    (workdir / "RUNNER.md").write_text(RUNNER_INSTRUCTIONS)

    if config["cli"] == "claude" and not (workdir / ".claude").exists():
        claude_dir = workdir / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text(json.dumps(CLAUDE_SETTINGS, indent=2) + "\n")

    command = _command(config, REFINEMENT_KICKOFF, workdir)
    transcript = workdir / "transcript-gen2-attempt-1.stream.jsonl"
    environment = _environment(arguments.truth_root, arguments.scorer_key_file)
    started = time.time()
    with transcript.open("w") as sink:
        completed = subprocess.run(
            command,
            cwd=workdir,
            stdin=subprocess.DEVNULL,
            stdout=sink,
            stderr=subprocess.PIPE,
            text=True,
            timeout=arguments.timeout_seconds,
            env=environment,
            check=False,
        )

    changed = (
        submission_path.read_bytes() != gen1_submission_backup.read_bytes()
        or final_predictions_path.read_bytes() != gen1_predictions_backup.read_bytes()
    )
    meta = {
        "suite_id": arguments.suite_id,
        "parent_run_id": arguments.run_id,
        "returncode": completed.returncode,
        "seconds": round(time.time() - started, 1),
        "stderr_tail": (completed.stderr or "")[-2000:],
        "predictions_changed_from_gen1": changed,
    }
    (output_dir / "gen2_meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    shutil.copy2(transcript, output_dir / transcript.name)
    if submission_path.exists():
        shutil.copy2(submission_path, output_dir / "agent_submission.json")
    if final_predictions_path.exists():
        shutil.copy2(final_predictions_path, output_dir / "final_predictions.csv")
    print(json.dumps({"ok": completed.returncode == 0, "meta": meta}, indent=2))


def _command(config: Mapping[str, str], prompt: str, workdir: Path) -> list[str]:
    if config["cli"] == "codex":
        effort = config.get("reasoning_effort", "xhigh")
        return [
            "codex",
            "exec",
            "--skip-git-repo-check",
            "--json",
            "-m",
            config["model"],
            "-c",
            f'model_reasoning_effort="{effort}"',
            "-s",
            "danger-full-access",
            "-C",
            str(workdir),
            prompt,
        ]
    if config["cli"] == "claude":
        return [
            "claude",
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
            "--model",
            config["model"],
            "--max-turns",
            "1000",
        ]
    raise SystemExit(f"unknown cli {config['cli']!r}")


def _environment(truth_root: Path, scorer_key_file: Path) -> dict[str, str]:
    keep = ("PATH", "HOME", "LANG", "TERM", "SHELL")
    environment = {name: os.environ[name] for name in keep if name in os.environ}
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        environment[name] = "2"
    environment["V044_TRUTH_ROOT"] = str(truth_root.resolve())
    environment["V044_KEY_FILE"] = str(scorer_key_file.resolve())
    return environment


if __name__ == "__main__":
    main()
