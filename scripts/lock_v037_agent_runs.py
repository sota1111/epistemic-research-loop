#!/usr/bin/env python3
"""Validate and hash-lock all 24 v0.3.7 agent runs before truth unblinding."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from epistemic_loop.benchmark.v037_repro_suite import V037_RUN_IDS, V037_SUITE_IDS
from epistemic_loop.controller.v037_agent import load_v037_submission, validate_v037_submission


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-root", type=Path, default=Path(".runs/v037"))
    parser.add_argument("--submission-root", type=Path, default=Path(".runs/v037/agent_outputs"))
    parser.add_argument("--lock-file", type=Path, default=Path(".runs/v037/all_agent_runs.lock.json"))
    arguments = parser.parse_args()
    if arguments.lock_file.exists():
        raise SystemExit("v0.3.7 agent outputs are already locked")
    records: list[dict[str, object]] = []
    errors: list[str] = []
    for suite_id in V037_SUITE_IDS:
        for run_id in V037_RUN_IDS:
            packet_path = arguments.suite_root / suite_id / "agent_views" / run_id / "agent_packet.json"
            submission_path = arguments.submission_root / suite_id / run_id / "agent_submission.json"
            try:
                packet = json.loads(packet_path.read_text())
                submission = load_v037_submission(submission_path)
                validation = validate_v037_submission(submission, packet)
            except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                errors.append(f"{suite_id}/{run_id}: {error}")
                continue
            errors.extend(f"{suite_id}/{run_id}: {item}" for item in validation.errors)
            records.append(
                {
                    "suite_id": suite_id,
                    "run_id": run_id,
                    "packet_sha256": _sha256(packet_path),
                    "submission_sha256": _sha256(submission_path),
                    "valid": validation.valid,
                }
            )
    if errors:
        print(json.dumps({"locked": False, "errors": errors}, indent=2))
        raise SystemExit(1)
    payload = {
        "version": "0.3.7",
        "all_outputs_locked_before_hidden_evaluation": True,
        "suite_count": len(V037_SUITE_IDS),
        "agent_run_count": len(records),
        "records": records,
    }
    arguments.lock_file.parent.mkdir(parents=True, exist_ok=True)
    arguments.lock_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    main()
