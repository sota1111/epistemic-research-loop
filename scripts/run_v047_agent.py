#!/usr/bin/env python3
"""Execute one v0.4.7 late-submission suite run.

Mirrors run_v044_agent.py's mechanics exactly (CLI dispatch via _command, the same
score_confirmation.py provisioning + V044_TRUTH_ROOT/V044_KEY_FILE env-var injection, the
same danger-full-access/--dangerously-skip-permissions isolation posture) -- see that
script's docstring for why. The one addition: v0.4.7 packets always include a
real_test.csv the agent must predict, so validation here also requires a
final_predictions.csv covering every row_id in real_test.csv (docs/c_lite_v047_policy.md
SS1/SS5) -- a file, not an inline JSON list, since real_test.csv can be hundreds of
thousands of rows.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import time
from collections.abc import Mapping
from pathlib import Path

from epistemic_loop.benchmark.v044_full_feature_pilot import V044_MAX_SCORER_CALLS
from epistemic_loop.benchmark.v047_kaggle_submission_suite import V047_CANDIDATE_CONFIGS

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

KICKOFF = (
    "You are executing a locked blind research protocol. Read agent_prompt.md, agent_packet.json, "
    "and RUNNER.md in the current directory. Then carry out the pilot for this pack and write "
    "agent_submission.json and final_predictions.csv here. Work autonomously and stay strictly "
    "inside this directory."
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
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--suite-root", type=Path, default=Path(".runs/v047"))
    parser.add_argument("--output-root", type=Path, default=Path(".runs/v047/agent_outputs"))
    parser.add_argument("--truth-root", type=Path, default=Path(".controller_truth/v047"))
    parser.add_argument("--scorer-key-file", type=Path, default=Path(".state/v044/scorer.key"))
    parser.add_argument("--workdir-root", type=Path, default=Path.home() / "erl-v047-runs")
    parser.add_argument("--timeout-seconds", type=float, default=10800)
    arguments = parser.parse_args()
    if arguments.run_id not in V047_CANDIDATE_CONFIGS:
        raise SystemExit(f"run id {arguments.run_id!r} has no preregistered v0.4.7 execution configuration")
    config = V047_CANDIDATE_CONFIGS[arguments.run_id]
    reasoning_effort = config.get("reasoning_effort")

    view_root = arguments.suite_root / arguments.suite_id / "agent_views" / arguments.run_id
    if not (view_root / "agent_packet.json").exists():
        raise SystemExit(f"missing built agent view: {view_root}")
    output_dir = arguments.output_root / arguments.suite_id / arguments.run_id
    if (output_dir / "agent_submission.json").exists():
        raise SystemExit(f"output already recorded for {arguments.suite_id}/{arguments.run_id}")

    packet = json.loads((view_root / "agent_packet.json").read_text())
    scoring_enabled = "confirmation_scorer_command" in packet

    workdir = arguments.workdir_root / arguments.suite_id / arguments.run_id
    if not workdir.exists():
        workdir.mkdir(parents=True)
        for item in view_root.iterdir():
            if item.is_dir():
                shutil.copytree(item, workdir / item.name)
            else:
                shutil.copy2(item, workdir / item.name)
        (workdir / "RUNNER.md").write_text(RUNNER_INSTRUCTIONS)
        if scoring_enabled:
            scorer_script = Path(__file__).parent / "v044_score_confirmation.py"
            shutil.copy2(scorer_script, workdir / "score_confirmation.py")
        if config["cli"] == "claude":
            claude_dir = workdir / ".claude"
            claude_dir.mkdir()
            (claude_dir / "settings.json").write_text(json.dumps(CLAUDE_SETTINGS, indent=2) + "\n")
    submission_path = workdir / "agent_submission.json"
    final_predictions_path = workdir / "final_predictions.csv"
    command = _command(config, KICKOFF, workdir)
    transcript = workdir / "transcript-attempt-1.stream.jsonl"
    environment = _environment(arguments.truth_root, arguments.scorer_key_file, scoring_enabled=scoring_enabled)
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
    errors = _validate(submission_path, final_predictions_path, workdir / "real_test.csv", packet)
    meta = {
        "suite_id": arguments.suite_id,
        "run_id": arguments.run_id,
        "reasoning_effort": reasoning_effort,
        "fresh_context": True,
        "returncode": completed.returncode,
        "seconds": round(time.time() - started, 1),
        "stderr_tail": (completed.stderr or "")[-2000:],
        "contract_valid": not errors,
        "contract_errors": list(errors)[:50],
        "max_scorer_calls": V044_MAX_SCORER_CALLS,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    shutil.copy2(transcript, output_dir / transcript.name)
    if errors:
        print(json.dumps({"ok": False, "errors": list(errors)[:20]}, indent=2))
        raise SystemExit(1)
    shutil.copy2(submission_path, output_dir / "agent_submission.json")
    shutil.copy2(final_predictions_path, output_dir / "final_predictions.csv")
    print(json.dumps({"ok": True, "output": str(output_dir / "agent_submission.json"), "meta": meta}, indent=2))


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


def _validate(
    submission_path: Path, final_predictions_path: Path, real_test_path: Path, packet: dict[str, object]
) -> tuple[str, ...]:
    if not submission_path.exists():
        return ("agent_submission.json was not produced",)
    try:
        payload = json.loads(submission_path.read_text())
    except json.JSONDecodeError as error:
        return (f"submission is not valid JSON: {error}",)
    errors: list[str] = []
    required_fields: tuple[str, ...] = ("version", "suite_id", "run_id", "approach_summary", "transfer_predictions")
    if "confirmation_scorer_command" in packet:
        required_fields = (*required_fields, "confirmation_calls_made")
    for field in required_fields:
        if field not in payload:
            errors.append(f"missing field: {field}")
    if errors:
        return tuple(errors)
    if payload["suite_id"] != packet["suite_id"] or payload["run_id"] != packet["run_id"]:
        errors.append("suite_id/run_id mismatch with packet")
    predictions = payload["transfer_predictions"]
    if not isinstance(predictions, list) or not predictions:
        errors.append("transfer_predictions must be a non-empty list")
    else:
        expected_rows = int(packet["transfer_rows"])
        if len(predictions) != expected_rows:
            errors.append(f"transfer_predictions has {len(predictions)} entries, expected {expected_rows}")
        for item in predictions:
            if not isinstance(item, dict) or "row_id" not in item or "prediction" not in item:
                errors.append("every transfer_predictions entry needs row_id and prediction")
                break
            if not isinstance(item["prediction"], int | float) or not 0 <= item["prediction"] <= 1:
                errors.append(f"prediction out of [0,1]: {item['prediction']!r}")
                break

    errors.extend(_validate_final_predictions(final_predictions_path, real_test_path))
    return tuple(errors)


def _validate_final_predictions(final_predictions_path: Path, real_test_path: Path) -> tuple[str, ...]:
    if not final_predictions_path.exists():
        return ("final_predictions.csv was not produced",)
    if not real_test_path.exists():
        return ("real_test.csv is missing from the workdir -- cannot validate coverage",)
    with real_test_path.open(newline="") as handle:
        expected_row_ids = {row["row_id"] for row in csv.DictReader(handle)}
    with final_predictions_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or {"row_id", "prediction"} - set(reader.fieldnames):
            return ("final_predictions.csv must have header: row_id,prediction",)
        rows = list(reader)
    errors: list[str] = []
    submitted_ids = {row["row_id"] for row in rows}
    missing = expected_row_ids - submitted_ids
    if missing:
        errors.append(f"final_predictions.csv is missing {len(missing)} row_ids from real_test.csv")
    if len(rows) != len(submitted_ids):
        errors.append("final_predictions.csv has duplicate row_id entries")
    for row in rows:
        try:
            value = float(row["prediction"])
        except ValueError:
            errors.append(f"non-numeric prediction for row_id {row['row_id']}: {row['prediction']!r}")
            break
        if not 0 <= value <= 1:
            errors.append(f"prediction out of [0,1] for row_id {row['row_id']}: {value!r}")
            break
    return tuple(errors)


def _environment(truth_root: Path, scorer_key_file: Path, *, scoring_enabled: bool) -> dict[str, str]:
    keep = ("PATH", "HOME", "LANG", "TERM", "SHELL")
    environment = {name: os.environ[name] for name in keep if name in os.environ}
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        environment[name] = "2"
    if scoring_enabled:
        environment["V044_TRUTH_ROOT"] = str(truth_root.resolve())
        environment["V044_KEY_FILE"] = str(scorer_key_file.resolve())
    return environment


if __name__ == "__main__":
    main()
