#!/usr/bin/env python3
"""Run one v0.4.4 suite's runs (V044_SOL_EFFORT_CONFIGS, 8 by default) with bounded parallelism.

Same resumable pattern as run_v042_batch.py: shells out to run_v044_agent.py per (suite,
run_id) pair, skipping pairs that already have a recorded agent_submission.json.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from epistemic_loop.benchmark.v044_full_feature_pilot import (
    V044_R2_RUN_IDS,
    V044_R3_RUN_IDS,
    V044_R4_RUN_IDS,
    V044_R5_RUN_IDS,
    V044_SOL_EFFORT_RUN_IDS,
)

_RUN_ID_SETS: dict[str, tuple[str, ...]] = {
    "screening": V044_SOL_EFFORT_RUN_IDS,
    "confirm": V044_R2_RUN_IDS,
    "scale": V044_R3_RUN_IDS,
    "10col-fb": V044_R4_RUN_IDS,
    "full-nofb": V044_R5_RUN_IDS,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-id", required=True)
    parser.add_argument("--config-set", default="screening", choices=sorted(_RUN_ID_SETS))
    parser.add_argument("--parallel", type=int, default=4)
    parser.add_argument("--suite-root", type=Path, default=Path(".runs/v044"))
    parser.add_argument("--output-root", type=Path, default=Path(".runs/v044/agent_outputs"))
    parser.add_argument("--timeout-seconds", type=float, default=10800)
    arguments = parser.parse_args()
    run_ids = _RUN_ID_SETS[arguments.config_set]
    pending = [
        run
        for run in run_ids
        if not (arguments.output_root / arguments.suite_id / run / "agent_submission.json").exists()
    ]
    print(f"{len(pending)} of {len(run_ids)} runs pending", flush=True)
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=arguments.parallel) as pool:
        futures = {pool.submit(_run_one, run, arguments): run for run in pending}
        for future in as_completed(futures):
            run = futures[future]
            code = future.result()
            status = "ok" if code == 0 else f"FAILED (exit {code})"
            print(f"[{arguments.suite_id}/{run}] {status}", flush=True)
            if code != 0:
                failures.append(f"{arguments.suite_id}/{run}")
    summary = {"study": "v044-full-feature-suite", "pending": len(pending), "failures": failures}
    print(json.dumps(summary, indent=2))
    if failures:
        raise SystemExit(1)


def _run_one(run: str, arguments: argparse.Namespace) -> int:
    command = [
        sys.executable,
        "scripts/run_v044_agent.py",
        "--suite-id",
        arguments.suite_id,
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
    log_dir = arguments.output_root / arguments.suite_id / run
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "batch_runner.log").write_text(
        (completed.stdout or "") + "\n--- stderr ---\n" + (completed.stderr or "")
    )
    return completed.returncode


if __name__ == "__main__":
    main()
