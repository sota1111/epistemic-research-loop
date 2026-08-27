#!/usr/bin/env python3
"""Audit all v0.3.7 agent-visible views before real-agent execution."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from epistemic_loop.benchmark.v037_repro_suite import V037_RUN_IDS, V037_SUITE_IDS, audit_v037_agent_view


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-root", type=Path, default=Path(".runs/v037"))
    parser.add_argument("--report", type=Path, default=Path(".runs/v037/blindness_report.json"))
    arguments = parser.parse_args()
    findings: dict[str, list[str]] = {}
    for suite_id in V037_SUITE_IDS:
        for run_id in V037_RUN_IDS:
            root = arguments.suite_root / suite_id / "agent_views" / run_id
            issues = list(audit_v037_agent_view(root))
            if issues:
                findings[f"{suite_id}/{run_id}"] = issues
    payload = {
        "version": "0.3.7",
        "views_audited": len(V037_SUITE_IDS) * len(V037_RUN_IDS),
        "controller_truth_leakage": sum(len(value) for value in findings.values()),
        "findings": findings,
        "passed": not findings,
    }
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))
    if findings:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
