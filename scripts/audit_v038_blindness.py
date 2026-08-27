#!/usr/bin/env python3
"""Audit v0.3.8 agent-visible views and run transcripts for truth leakage.

Two surfaces are audited:

1. Every agent-visible file in every run view, for canonical family names and
   truth-only field names (same token list as v0.3.7).
2. Every retained `claude -p` stream transcript, for forbidden-path access
   (controller truth, keys, the repository itself) and for the same tokens.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from epistemic_loop.benchmark.v037_repro_suite import audit_v037_agent_view
from epistemic_loop.benchmark.v038_repro_suite import (
    V038_DEV_SUITE_IDS,
    V038_QUAL_SUITE_IDS,
    V038_RUN_IDS,
)

TRANSCRIPT_FORBIDDEN = (
    ".controller_truth",
    "controller.key",
    "manifest.enc",
    "/workspaces/epistemic-research-loop",
    "structure_present",
    "persistent_clear",
    "persistent_noisy_proxy",
    "persistent_delayed_history",
    "persistent_compositional",
    "matched_nonpersistent",
    "observation_routing_composition",
    "stable_structure_nonactionable",
    "useful_encoding_without_structure",
    "random_routing_surface",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-root", type=Path, default=Path(".runs/v038"))
    parser.add_argument("--submission-root", type=Path, default=Path(".runs/v038/agent_outputs"))
    arguments = parser.parse_args()
    view_findings: list[str] = []
    audited_views = 0
    for suite_id in (*V038_QUAL_SUITE_IDS, *V038_DEV_SUITE_IDS):
        for run_id in V038_RUN_IDS:
            root = arguments.suite_root / suite_id / "agent_views" / run_id
            if not root.exists():
                continue
            audited_views += 1
            view_findings.extend(f"{suite_id}/{run_id}/{item}" for item in audit_v037_agent_view(root))
    transcript_findings: list[str] = []
    audited_transcripts = 0
    for transcript in sorted(arguments.submission_root.rglob("transcript-attempt-*.stream.jsonl")):
        audited_transcripts += 1
        text = transcript.read_text(errors="ignore")
        for token in TRANSCRIPT_FORBIDDEN:
            count = text.count(token)
            if count:
                transcript_findings.append(f"{transcript.relative_to(arguments.submission_root)}: {token} x{count}")
    payload = {
        "audited_views": audited_views,
        "view_findings": view_findings,
        "audited_transcripts": audited_transcripts,
        "transcript_findings": transcript_findings,
        "clean": not view_findings and not transcript_findings,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if view_findings or transcript_findings:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
