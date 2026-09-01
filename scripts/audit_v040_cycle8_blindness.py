#!/usr/bin/env python3
"""Audit the cycle-budget ablation's agent-visible views and transcripts.

Same two surfaces and token list as the other v0.4.0 blindness audits, scoped to this
study's own suite/run ids.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from epistemic_loop.benchmark.v037_repro_suite import audit_v037_agent_view
from epistemic_loop.benchmark.v040_grammar_suite import (
    GRAMMAR_FAMILY_TOKENS,
    V040_CYCLE8_RUN_IDS,
    V040_CYCLE8_SUITE_IDS,
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
    *GRAMMAR_FAMILY_TOKENS,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-root", type=Path, default=Path(".runs/v040"))
    parser.add_argument("--submission-root", type=Path, default=Path(".runs/v040/agent_outputs"))
    arguments = parser.parse_args()
    view_findings: list[str] = []
    audited_views = 0
    for suite_id in V040_CYCLE8_SUITE_IDS:
        for run_id in V040_CYCLE8_RUN_IDS:
            root = arguments.suite_root / suite_id / "agent_views" / run_id
            if not root.exists():
                continue
            audited_views += 1
            view_findings.extend(f"{suite_id}/{run_id}/{item}" for item in audit_v037_agent_view(root))
    transcript_findings: list[str] = []
    audited_transcripts = 0
    for suite_id in V040_CYCLE8_SUITE_IDS:
        for transcript in sorted((arguments.submission_root / suite_id).rglob("transcript-attempt-*.stream.jsonl")):
            audited_transcripts += 1
            text = transcript.read_text(errors="ignore")
            # Same interpreter-path allow-list as every prior v0.4.0 audit.
            text = text.replace("/workspaces/epistemic-research-loop/.venv/", "<interpreter-venv>/")
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
