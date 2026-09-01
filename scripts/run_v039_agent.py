#!/usr/bin/env python3
"""Execute one fresh-context v0.3.9 agent run through the `claude -p` CLI.

One invocation = one (suite, run) pair = one fresh LLM context. The agent view is
copied into an isolated working directory outside the repository, the CLI is started
with deny rules against the repository and controller paths, the full stream-json
transcript is retained for the blindness audit, and the produced submission is
contract-validated before it is copied back for locking. Contract-validation
feedback (never truth) may be fed back for a bounded number of repair attempts.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from epistemic_loop.controller.v039_agent import load_v039_submission, validate_v039_submission

RUNNER_INSTRUCTIONS = """# Operational rules for this research run

- Work ONLY inside this directory. Never read, list, or write files outside it. Never use the
  network. Never look for controller code, truth manifests, keys, or other agents' work.
- `agent_prompt.md` is the binding research prompt. `agent_packet.json` lists your data packs.
  `submission_contract.json` is the exact output schema.
- Write your final output to `agent_submission.json` in this directory with `version` `0.3.9`.
- Keep your analysis code in this directory (any layout). Use deterministic seeds.
- python3 is available. Prefer simple, capacity-matched models; the datasets are small
  (hundreds of rows per context file). Vectorize where possible and avoid long hyperparameter
  searches; the whole run should finish well within your session.
- Every executed null replicate must regenerate features and refit the model, and must be
  recorded in `null_summary.replicates` with: replicate_index, permutation_hash,
  preserved_statistics (name -> finite number), feature_manifest_hash, fold_plan_hash,
  model_fit_manifest_hash, oof_prediction_hash, gain. Hashes are lowercase sha256 hex digests
  computed over the corresponding artifacts you actually produced. The gain values must equal
  `replicate_gains` entry-by-entry.
- Your lineage policy is stated in `agent_packet.json` and is binding as described in the
  research prompt.
- A terminal resolution must be internally consistent with your own artifacts: a falsified
  pack may report an independent implication strength above 0.05 in at most one context and
  research gains above your own null 95th percentile in at most one context; a validated pack
  must report implication strengths above 0.05 in at least two contexts.
- Predictions for `.confirmation.json` and `.transfer.json` files must be aligned to the row
  order of those files and must come from models fit on research labels only.
"""

KICKOFF = (
    "You are executing a locked blind research protocol. Read agent_prompt.md, agent_packet.json, "
    "submission_contract.json, and RUNNER.md in the current directory. Then carry out the complete "
    "protocol for every pack in the packet and write agent_submission.json here. Work autonomously "
    "and stay strictly inside this directory."
)

SETTINGS = {
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
    parser.add_argument("--suite-root", type=Path, default=Path(".runs/v039"))
    parser.add_argument("--output-root", type=Path, default=Path(".runs/v039/agent_outputs"))
    parser.add_argument("--workdir-root", type=Path, default=Path.home() / "erl-v039-runs")
    parser.add_argument("--model", default="opus")
    parser.add_argument("--timeout-seconds", type=float, default=10800)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--max-turns", type=int, default=1000)
    arguments = parser.parse_args()

    view_root = arguments.suite_root / arguments.suite_id / "agent_views" / arguments.run_id
    if not (view_root / "agent_packet.json").exists():
        raise SystemExit(f"missing locked agent view: {view_root}")
    output_dir = arguments.output_root / arguments.suite_id / arguments.run_id
    if (output_dir / "agent_submission.json").exists():
        raise SystemExit(f"output already recorded for {arguments.suite_id}/{arguments.run_id}")

    workdir = arguments.workdir_root / arguments.suite_id / arguments.run_id
    if not workdir.exists():
        workdir.mkdir(parents=True)
        for item in view_root.iterdir():
            if item.is_dir():
                shutil.copytree(item, workdir / item.name)
            else:
                shutil.copy2(item, workdir / item.name)
        (workdir / "RUNNER.md").write_text(RUNNER_INSTRUCTIONS)
        claude_dir = workdir / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text(json.dumps(SETTINGS, indent=2) + "\n")

    packet = json.loads((view_root / "agent_packet.json").read_text())
    attempts: list[dict[str, object]] = []
    submission_path = workdir / "agent_submission.json"
    errors: tuple[str, ...] = ()
    for attempt in range(1, arguments.max_attempts + 1):
        prompt = KICKOFF if attempt == 1 else _repair_prompt(errors)
        command = ["claude"]
        if attempt > 1:
            command.append("--continue")
        command += [
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
            "--model",
            arguments.model,
            "--max-turns",
            str(arguments.max_turns),
        ]
        transcript = workdir / f"transcript-attempt-{attempt}.stream.jsonl"
        started = time.time()
        with transcript.open("w") as sink:
            completed = subprocess.run(
                command,
                cwd=workdir,
                stdout=sink,
                stderr=subprocess.PIPE,
                text=True,
                timeout=arguments.timeout_seconds,
                env=_environment(),
                check=False,
            )
        attempts.append(
            {
                "attempt": attempt,
                "returncode": completed.returncode,
                "seconds": round(time.time() - started, 1),
                "stderr_tail": (completed.stderr or "")[-2000:],
            }
        )
        errors = _validate(submission_path, packet)
        if not errors:
            break
    else:
        pass

    meta = {
        "suite_id": arguments.suite_id,
        "run_id": arguments.run_id,
        "model": arguments.model,
        "fresh_context": True,
        "attempts": attempts,
        "contract_valid": not errors,
        "contract_errors": list(errors)[:50],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    for transcript in sorted(workdir.glob("transcript-attempt-*.stream.jsonl")):
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
        loaded = load_v039_submission(submission_path)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        return (f"submission failed to parse: {error}",)
    return validate_v039_submission(loaded, packet).errors


def _repair_prompt(errors: tuple[str, ...]) -> str:
    listed = "\n".join(f"- {item}" for item in errors[:25])
    return (
        "Your agent_submission.json did not satisfy the locked contract. This is contract "
        "validation feedback only; it contains no information about the data. Fix exactly these "
        f"issues and rewrite agent_submission.json:\n{listed}"
    )


def _environment() -> dict[str, str]:
    # The CLI authenticates itself; never forward provider API keys into the agent process.
    keep = ("PATH", "HOME", "LANG", "TERM", "SHELL")
    environment = {name: os.environ[name] for name in keep if name in os.environ}
    # Parallel runs previously hit BLAS thread contention (v0.3.7 trial log); pin the
    # numerical libraries inside every agent's python processes to two threads.
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        environment[name] = "2"
    return environment


if __name__ == "__main__":
    main()
