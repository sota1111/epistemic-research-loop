#!/usr/bin/env python3
"""Run one v0.4.2 suite's 12 runs (3 execution configs x 4 replicates) with bounded parallelism.

Generic across competitions; same resumable pattern as run_v041_track_b_batch.py.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from epistemic_loop.benchmark.v042_multi_competition_suite import V042_RUN_IDS


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-id", required=True)
    parser.add_argument("--parallel", type=int, default=3)
    parser.add_argument("--suite-root", type=Path, default=Path(".runs/v042"))
    parser.add_argument("--output-root", type=Path, default=Path(".runs/v042/agent_outputs"))
    parser.add_argument("--timeout-seconds", type=float, default=10800)
    arguments = parser.parse_args()
    pairs = [(arguments.suite_id, run) for run in V042_RUN_IDS]
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
    summary = {"study": "v042-multi-competition-blind-bridge", "pending": len(pending), "failures": failures}
    print(json.dumps(summary, indent=2))
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
        "--suite-root",
        str(arguments.suite_root),
        "--output-root",
        str(arguments.output_root),
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
