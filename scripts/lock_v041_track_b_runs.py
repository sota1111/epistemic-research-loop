#!/usr/bin/env python3
"""Validate and hash-lock Track B's 12 runs before the truth manifest is opened."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from epistemic_loop.benchmark.v041_track_b_suite import V041_TRACKB_RUN_IDS, V041_TRACKB_SUITE_ID
from epistemic_loop.controller.v040_agent import load_v040_submission, validate_v040_submission


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-root", type=Path, default=Path(".runs/v041"))
    parser.add_argument("--submission-root", type=Path, default=Path(".runs/v041/agent_outputs"))
    arguments = parser.parse_args()
    lock_file = arguments.suite_root / "trackb_agent_runs.lock.json"
    if lock_file.exists():
        raise SystemExit("Track B outputs are already locked")
    records: list[dict[str, object]] = []
    errors: list[str] = []
    for run_id in V041_TRACKB_RUN_IDS:
        packet_path = arguments.suite_root / V041_TRACKB_SUITE_ID / "agent_views" / run_id / "agent_packet.json"
        submission_path = arguments.submission_root / V041_TRACKB_SUITE_ID / run_id / "agent_submission.json"
        try:
            packet = json.loads(packet_path.read_text())
            loaded = load_v040_submission(submission_path)
            validation = validate_v040_submission(loaded, packet)
        except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            errors.append(f"{V041_TRACKB_SUITE_ID}/{run_id}: {error}")
            continue
        errors.extend(f"{V041_TRACKB_SUITE_ID}/{run_id}: {item}" for item in validation.errors)
        transcripts = sorted(submission_path.parent.glob("transcript-attempt-*.stream.jsonl"))
        records.append(
            {
                "suite_id": V041_TRACKB_SUITE_ID,
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
        "version": "0.4.0",
        "study": "track-b-ieee-cis-blind-bridge",
        "all_outputs_locked_before_hidden_evaluation": True,
        "agent_run_count": len(records),
        "records": records,
    }
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"locked": True, "study": "track-b-ieee-cis-blind-bridge", "runs": len(records)}, indent=2))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    main()
