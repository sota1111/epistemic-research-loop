#!/usr/bin/env python3
"""Audit the v0.3.6 agent-visible boundary without decrypting controller truth."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from epistemic_loop.benchmark.v036_blind_suite import DEFAULT_AGENTS, audit_agent_view


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=Path("docs/v036_development_suite_report.json"))
    arguments = parser.parse_args()
    findings: dict[str, list[str]] = {}
    packet_hashes: dict[str, str] = {}
    for agent in DEFAULT_AGENTS:
        root = arguments.suite_root / "agent_views" / agent
        findings[agent] = list(audit_agent_view(root))
        packet_hashes[agent] = hashlib.sha256((root / "agent_packet.json").read_bytes()).hexdigest()
    controller_files_in_view = [
        str(path.relative_to(arguments.suite_root))
        for path in arguments.suite_root.rglob("*")
        if path.is_file() and (path.suffix in {".enc", ".key"} or "truth" in path.name.lower())
    ]
    result = {
        "version": "0.3.6",
        "suite_root": str(arguments.suite_root),
        "agent_findings": findings,
        "controller_files_in_agent_tree": controller_files_in_view,
        "packet_hashes": packet_hashes,
        "controller_truth_leakage": sum(len(items) for items in findings.values()) + len(controller_files_in_view),
        "passed": not any(findings.values()) and not controller_files_in_view,
        "boundary_note": "content and path audit; runtime is policy-isolated on the shared development host",
    }
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
