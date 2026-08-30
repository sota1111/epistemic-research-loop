#!/usr/bin/env python3
"""Validate and hash-lock a v0.4.2 suite's 12 runs before the truth manifest is opened."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from epistemic_loop.benchmark.v042_multi_competition_suite import (
    V042_RUN_IDS,
    V043_SOL_EFFORT_R2_IEEE_CIS_RUN_IDS,
    V043_SOL_EFFORT_R2_SANTANDER_RUN_IDS,
    V043_SOL_EFFORT_R3_IEEE_CIS_RUN_IDS,
    V043_SOL_EFFORT_R3_SANTANDER_RUN_IDS,
    V043_SOL_EFFORT_RUN_IDS,
)
from epistemic_loop.controller.v040_agent import load_v040_submission, validate_v040_submission

_RUN_ID_SETS: dict[str, tuple[str, ...]] = {
    "default": V042_RUN_IDS,
    "sol-effort": V043_SOL_EFFORT_RUN_IDS,
    "sol-effort-r2-a": V043_SOL_EFFORT_R2_IEEE_CIS_RUN_IDS,
    "sol-effort-r2-b": V043_SOL_EFFORT_R2_SANTANDER_RUN_IDS,
    "sol-effort-r3-a": V043_SOL_EFFORT_R3_IEEE_CIS_RUN_IDS,
    "sol-effort-r3-b": V043_SOL_EFFORT_R3_SANTANDER_RUN_IDS,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-id", required=True)
    parser.add_argument("--config-set", default="default", choices=sorted(_RUN_ID_SETS))
    parser.add_argument("--suite-root", type=Path, default=Path(".runs/v042"))
    parser.add_argument("--submission-root", type=Path, default=Path(".runs/v042/agent_outputs"))
    arguments = parser.parse_args()
    lock_file = arguments.suite_root / f"{arguments.suite_id}_agent_runs.lock.json"
    if lock_file.exists():
        raise SystemExit(f"suite outputs for {arguments.suite_id} are already locked")
    records: list[dict[str, object]] = []
    errors: list[str] = []
    for run_id in _RUN_ID_SETS[arguments.config_set]:
        packet_path = arguments.suite_root / arguments.suite_id / "agent_views" / run_id / "agent_packet.json"
        submission_path = arguments.submission_root / arguments.suite_id / run_id / "agent_submission.json"
        try:
            packet = json.loads(packet_path.read_text())
            loaded = load_v040_submission(submission_path)
            validation = validate_v040_submission(loaded, packet)
        except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            errors.append(f"{arguments.suite_id}/{run_id}: {error}")
            continue
        errors.extend(f"{arguments.suite_id}/{run_id}: {item}" for item in validation.errors)
        transcripts = sorted(submission_path.parent.glob("transcript-attempt-*.stream.jsonl"))
        records.append(
            {
                "suite_id": arguments.suite_id,
                "run_id": run_id,
                "packet_sha256": _sha256(packet_path),
                "submission_sha256": _sha256(submission_path),
                "transcript_sha256": {path.name: _sha256(path) for path in transcripts},
                "valid": validation.valid,
            }
        )
    if errors:
        print(json.dumps({"locked": False, "errors": errors}, indent=2))
        raise SystemExit(1)
    payload = {
        "version": "0.4.2",
        "study": "v042-multi-competition-blind-bridge",
        "suite_id": arguments.suite_id,
        "all_outputs_locked_before_hidden_evaluation": True,
        "agent_run_count": len(records),
        "records": records,
    }
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"locked": True, "suite_id": arguments.suite_id, "runs": len(records)}, indent=2))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    main()
