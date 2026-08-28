#!/usr/bin/env python3
"""Run a v0.4.0 generation-1 agent group (development or qualification) with bounded parallelism.

Each (suite, run) pair is executed by `scripts/run_v040_agent.py` as its own fresh
`claude -p` process. Completed pairs (a recorded agent_submission.json) are skipped,
so the batch is safely resumable.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from epistemic_loop.benchmark.v040_grammar_suite import (
    V040_GEN1_EXCLUDED_RUNS,
    V040_GEN1_SUITE_IDS,
    V040_RUN_IDS,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", choices=("qualification",), default="qualification")
    parser.add_argument("--parallel", type=int, default=3)
    parser.add_argument("--output-root", type=Path, default=Path(".runs/v040/agent_outputs"))
    parser.add_argument("--timeout-seconds", type=float, default=10800)
    arguments = parser.parse_args()
    pairs = [
        (suite, run)
        for suite in V040_GEN1_SUITE_IDS
        for run in V040_RUN_IDS
        if (suite, run) not in V040_GEN1_EXCLUDED_RUNS
    ]
    pending = [
        (suite, run)
        for suite, run in pairs
        if not (arguments.output_root / suite / run / "agent_submission.json").exists()
    ]
    print(f"{len(pending)} of {len(pairs)} runs pending", flush=True)
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=arguments.parallel) as pool:
        futures = {pool.submit(_run_one, suite, run, arguments): (suite, run) for suite, run in pending}
        for future in as_completed(futures):
            suite, run = futures[future]
            code = future.result()
            status = "ok" if code == 0 else f"FAILED (exit {code})"
            print(f"[{suite}/{run}] {status}", flush=True)
            if code != 0:
                failures.append(f"{suite}/{run}")
    print(json.dumps({"group": arguments.group, "pending": len(pending), "failures": failures}, indent=2))
    if failures:
        raise SystemExit(1)


def _run_one(suite: str, run: str, arguments: argparse.Namespace) -> int:
    command = [
        sys.executable,
        "scripts/run_v040_agent.py",
        "--suite-id",
        suite,
        "--run-id",
        run,
        "--timeout-seconds",
        str(arguments.timeout_seconds),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    log_dir = arguments.output_root / suite / run
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "batch_runner.log").write_text(
        (completed.stdout or "") + "\n--- stderr ---\n" + (completed.stderr or "")
    )
    return completed.returncode


if __name__ == "__main__":
    main()
