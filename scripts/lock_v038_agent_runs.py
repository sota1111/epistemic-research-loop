#!/usr/bin/env python3
"""Validate and hash-lock v0.3.8 agent runs (development or qualification group)."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from epistemic_loop.benchmark.v038_repro_suite import (
    V038_DEV_EXECUTED_RUN_IDS,
    V038_QUAL_SUITE_IDS,
    V038_RUN_IDS,
)
from epistemic_loop.controller.v038_agent import load_v038_submission, validate_v038_submission


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", choices=("development", "qualification"), required=True)
    parser.add_argument("--suite-root", type=Path, default=Path(".runs/v038"))
    parser.add_argument("--submission-root", type=Path, default=Path(".runs/v038/agent_outputs"))
    arguments = parser.parse_args()
    lock_file = arguments.suite_root / f"{arguments.group}_agent_runs.lock.json"
    if lock_file.exists():
        raise SystemExit(f"v0.3.8 {arguments.group} outputs are already locked")
    if arguments.group == "development":
        pairs = [(suite, run) for suite, runs in V038_DEV_EXECUTED_RUN_IDS.items() for run in runs]
    else:
        pairs = [(suite, run) for suite in V038_QUAL_SUITE_IDS for run in V038_RUN_IDS]
    records: list[dict[str, object]] = []
    errors: list[str] = []
    for suite_id, run_id in pairs:
        packet_path = arguments.suite_root / suite_id / "agent_views" / run_id / "agent_packet.json"
        submission_path = arguments.submission_root / suite_id / run_id / "agent_submission.json"
        try:
            packet = json.loads(packet_path.read_text())
            loaded = load_v038_submission(submission_path)
            validation = validate_v038_submission(loaded, packet)
        except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            errors.append(f"{suite_id}/{run_id}: {error}")
            continue
        errors.extend(f"{suite_id}/{run_id}: {item}" for item in validation.errors)
        transcripts = sorted((submission_path.parent).glob("transcript-attempt-*.stream.jsonl"))
        records.append(
            {
                "suite_id": suite_id,
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
        "version": "0.3.8",
        "group": arguments.group,
        "all_outputs_locked_before_hidden_evaluation": True,
        "agent_run_count": len(records),
        "records": records,
    }
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"locked": True, "group": arguments.group, "runs": len(records)}, indent=2))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    main()
