#!/usr/bin/env python3
"""Validate and freeze three autonomous v0.3.6 real-agent submissions."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from epistemic_loop.benchmark.v036_blind_suite import DEFAULT_AGENTS
from epistemic_loop.controller.v036_real_agent import (
    load_real_agent_submission,
    validate_submission_against_packet,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-root", type=Path, required=True)
    parser.add_argument("--submission-root", type=Path, required=True)
    parser.add_argument("--lock-file", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.lock_file.exists():
        raise SystemExit("Phase 1 outputs are already locked")
    records: list[dict[str, object]] = []
    failures: list[str] = []
    for agent in DEFAULT_AGENTS:
        packet_path = arguments.suite_root / "agent_views" / agent / "agent_packet.json"
        submission_path = arguments.submission_root / agent / "agent_submission.json"
        packet = json.loads(packet_path.read_text())
        try:
            submission = load_real_agent_submission(submission_path)
            validation = validate_submission_against_packet(submission, packet)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            failures.append(f"{agent}: {error}")
            continue
        if not validation.valid:
            failures.extend(f"{agent}: {error}" for error in validation.errors)
        records.append(
            {
                "agent_id": agent,
                "packet_sha256": hashlib.sha256(packet_path.read_bytes()).hexdigest(),
                "submission_sha256": hashlib.sha256(submission_path.read_bytes()).hexdigest(),
                "submission_path": str(submission_path),
                "valid": validation.valid,
                "errors": validation.errors,
            }
        )
    if failures:
        print(json.dumps({"locked": False, "errors": failures}, indent=2))
        raise SystemExit(1)
    payload = {
        "version": "0.3.6",
        "suite_id": records
        and json.loads((arguments.suite_root / "agent_views" / DEFAULT_AGENTS[0] / "agent_packet.json").read_text())[
            "suite_id"
        ],
        "phase": "independent_real_agent_qualification",
        "agent_count": len(records),
        "all_outputs_locked_before_unblinding": True,
        "records": records,
    }
    arguments.lock_file.parent.mkdir(parents=True, exist_ok=True)
    arguments.lock_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
