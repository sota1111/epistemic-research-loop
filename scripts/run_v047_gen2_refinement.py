#!/usr/bin/env python3
"""Run one v0.4.7 generation-2 "evolution" refinement, building on a completed run.

Copies the parent run_id's completed workdir (same column salt, same saved
scripts/pickles/agent_submission.json/final_predictions.csv left over from generation 1)
into a fresh child workdir and continues from there -- the whole point is that this
agent's own prior code already applies unchanged (docs/c_lite_v047_policy.md SS2.2;
docs/c_lite_v048_policy.md SS2 for the real-score-informed version). Multiple children
can be spawned from the same parent (--child-run-id distinct from --parent-run-id) for
independent replicate refinement attempts, since even the same model/prompt can diverge
across invocations. Backs up the generation-1 outputs in the child's own copy before
re-invoking, so both are preserved for comparison. Only overwrites
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
#: _command/CLAUDE_SETTINGS below). Written into the child workdir before every gen2
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


def _kickoff(real_score_note: str | None) -> str:
    score_paragraph = ""
    if real_score_note:
        score_paragraph = (
            "\n\nExternal feedback on your prior submission: "
            + real_score_note
            + " Use this as a genuine, real-world data point -- not a proxy score -- when "
            "deciding what to try next."
        )
    return (
        "You are continuing a research task in this SAME directory -- your own prior work is "
        "already here (copied from your own earlier attempt). Read agent_submission.json (your "
        "own approach_summary and confirmation results from your first pass) and inspect the "
        "scripts/models you already left behind. Your goal now: deliberately try to find a "
        "genuinely better approach than the one you already submitted -- new features, "
        "different model families, a more careful attack on your own current best approach, "
        "better ensembling, whatever you judge promising. Use ./score_confirmation.py again if "
        "useful (it remembers your prior call count)."
        + score_paragraph
        + " If, and only if, you find something that beats your prior confirmation score, "
        "overwrite agent_submission.json and final_predictions.csv with the improved approach "
        "and explain in approach_summary exactly what changed and why you believe it is better. "
        "If you do NOT find an improvement, say so explicitly in approach_summary and leave "
        "agent_submission.json and final_predictions.csv exactly as they were -- do not regress."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-id", required=True)
    parser.add_argument("--parent-run-id", required=True, help="the completed generation-1 run_id to build on")
    parser.add_argument(
        "--child-run-id",
        default=None,
        help="run_id for this refinement attempt's own workdir (defaults to --parent-run-id, i.e. in-place)",
    )
    parser.add_argument("--real-score-note", default=None, help="free text describing the parent's real Kaggle score")
    parser.add_argument("--output-root", type=Path, default=Path(".runs/v047/agent_outputs"))
    parser.add_argument("--truth-root", type=Path, default=Path(".controller_truth/v047"))
    parser.add_argument("--scorer-key-file", type=Path, default=Path(".state/v044/scorer.key"))
    parser.add_argument("--workdir-root", type=Path, default=Path.home() / "erl-v047-runs")
    parser.add_argument("--timeout-seconds", type=float, default=10800)
    arguments = parser.parse_args()
    if arguments.parent_run_id not in V047_CANDIDATE_CONFIGS:
        raise SystemExit(f"run id {arguments.parent_run_id!r} has no preregistered v0.4.7 execution configuration")
    config = V047_CANDIDATE_CONFIGS[arguments.parent_run_id]
    child_run_id = arguments.child_run_id or arguments.parent_run_id

    parent_workdir = arguments.workdir_root / arguments.suite_id / arguments.parent_run_id
    parent_submission_path = parent_workdir / "agent_submission.json"
    parent_predictions_path = parent_workdir / "final_predictions.csv"
    if not parent_submission_path.exists() or not parent_predictions_path.exists():
        raise SystemExit(
            f"parent run {arguments.suite_id}/{arguments.parent_run_id} has no completed generation-1 output"
        )

    workdir = arguments.workdir_root / arguments.suite_id / child_run_id
    if child_run_id != arguments.parent_run_id:
        if workdir.exists():
            raise SystemExit(f"child workdir already exists: {workdir}; choose a different --child-run-id")
        shutil.copytree(parent_workdir, workdir)
    submission_path = workdir / "agent_submission.json"
    final_predictions_path = workdir / "final_predictions.csv"

    output_dir = arguments.output_root / arguments.suite_id / child_run_id / "gen2"
    if (output_dir / "agent_submission.json").exists():
        raise SystemExit(f"gen2 output already recorded for {arguments.suite_id}/{child_run_id}")
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

    prompt = _kickoff(arguments.real_score_note)
    command = _command(config, prompt, workdir)
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
        "parent_run_id": arguments.parent_run_id,
        "child_run_id": child_run_id,
        "real_score_note": arguments.real_score_note,
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
