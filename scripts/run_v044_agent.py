#!/usr/bin/env python3
"""Execute one v0.4.4 full-feature suite run through codex (sol).

One invocation = one (suite, run_id) pair = one fresh sol context (see
docs/verification/v044_full_feature_pilot_preregistration.md and c_lite_v044_policy.md).
Mirrors run_v040_agent.py's codex invocation mechanics (danger-full-access, pinned
reasoning effort, isolation via workdir-copy + instructions + post-hoc audit only, exactly
the same posture -- see that script's comments for why). Sol/codex only -- this study never
uses claude or glm. Two additions beyond run_v040_agent.py: this copies
scripts/v044_score_confirmation.py into the agent's own workdir (as score_confirmation.py,
a relative-path tool, never told the real repo location) and injects the two paths it
needs (V044_TRUTH_ROOT, V044_KEY_FILE) via environment variables rather than writing them
into any agent-visible file -- see that script's own docstring for why. run_id's execution
config (reasoning_effort, prompt_arm) is resolved from V044_SOL_EFFORT_CONFIGS, not passed
on the command line, matching every other suite in this project.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from epistemic_loop.benchmark.v044_full_feature_pilot import (
    V044_MAX_SCORER_CALLS,
    V044_R2_CONFIGS,
    V044_R3_CONFIGS,
    V044_R4_CONFIGS,
    V044_R5_CONFIGS,
    V044_SOL_EFFORT_CONFIGS,
)

_ALL_CONFIGS = {
    **V044_SOL_EFFORT_CONFIGS,
    **V044_R2_CONFIGS,
    **V044_R3_CONFIGS,
    **V044_R4_CONFIGS,
    **V044_R5_CONFIGS,
}

RUNNER_INSTRUCTIONS = """# Operational rules for this research run

- Work ONLY inside this directory. Never read, list, or write files outside it. Never use the
  network, except for invoking `./score_confirmation.py` (a local, offline tool -- not
  internet access).
- `agent_prompt.md` is the binding research prompt. `agent_packet.json` describes the data
  files and the scoring tool's exact invocation command.
- Write your final output to `agent_submission.json` in this directory.
- python3 is available. Keep your analysis code in this directory.
"""

KICKOFF = (
    "You are executing a locked blind research protocol. Read agent_prompt.md, agent_packet.json, "
    "and RUNNER.md in the current directory. Then carry out the pilot for this pack and write "
    "agent_submission.json here. Work autonomously and stay strictly inside this directory."
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--suite-root", type=Path, default=Path(".runs/v044"))
    parser.add_argument("--output-root", type=Path, default=Path(".runs/v044/agent_outputs"))
    parser.add_argument("--truth-root", type=Path, default=Path(".controller_truth/v044"))
    parser.add_argument("--scorer-key-file", type=Path, default=Path(".state/v044/scorer.key"))
    parser.add_argument("--workdir-root", type=Path, default=Path.home() / "erl-v044-runs")
    parser.add_argument("--timeout-seconds", type=float, default=10800)
    arguments = parser.parse_args()
    if arguments.run_id not in _ALL_CONFIGS:
        raise SystemExit(f"run id {arguments.run_id!r} has no preregistered v0.4.4 execution configuration")
    reasoning_effort = _ALL_CONFIGS[arguments.run_id]["reasoning_effort"]

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
    submission_path = workdir / "agent_submission.json"
    command = [
        "codex",
        "exec",
        "--skip-git-repo-check",
        "--json",
        "-m",
        "gpt-5.6-sol",
        "-c",
        f'model_reasoning_effort="{reasoning_effort}"',
        "-s",
        "danger-full-access",
        "-C",
        str(workdir),
        KICKOFF,
    ]
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
    errors = _validate(submission_path, packet)
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
    print(json.dumps({"ok": True, "output": str(output_dir / "agent_submission.json"), "meta": meta}, indent=2))


def _validate(submission_path: Path, packet: dict[str, object]) -> tuple[str, ...]:
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
        return tuple(errors)
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
