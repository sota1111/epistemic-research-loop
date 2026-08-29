#!/usr/bin/env python3
"""Audit Track B's agent-visible views (and, once runs exist, transcripts).

Same two-surface pattern as every v0.4.0 blindness audit, plus real-dataset-identifying
tokens specific to Track B (raw column names before hashing, dataset/company names,
the family labels this study invented for its own candidate/matched-negative packs).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from epistemic_loop.benchmark.v037_repro_suite import audit_v037_agent_view
from epistemic_loop.benchmark.v041_track_b_suite import V041_TRACKB_RUN_IDS, V041_TRACKB_SUITE_ID

FORBIDDEN_TOKENS = (
    ".controller_truth",
    "controller.key",
    "manifest.enc",
    "/workspaces/epistemic-research-loop",
    "structure_present",
    "predictive_utility",
    "generator_seed",
    "confirmation_targets",
    "transfer_targets",
    "real_candidate",
    "real_matched_negative",
    "isFraud",
    "TransactionID",
    "TransactionDT",
    "ieee-cis",
    "ieee_cis",
    "IEEE-CIS",
    "Vesta",
    ".data/ieee-cis",
    "train_transaction",
    "train_identity",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-root", type=Path, default=Path(".runs/v041"))
    parser.add_argument("--submission-root", type=Path, default=Path(".runs/v041/agent_outputs"))
    arguments = parser.parse_args()
    view_findings: list[str] = []
    audited_views = 0
    for run_id in V041_TRACKB_RUN_IDS:
        root = arguments.suite_root / V041_TRACKB_SUITE_ID / "agent_views" / run_id
        if not root.exists():
            continue
        audited_views += 1
        view_findings.extend(f"{run_id}/{item}" for item in audit_v037_agent_view(root))
        text = "\n".join(path.read_text(errors="ignore") for path in root.rglob("*") if path.is_file())
        for token in FORBIDDEN_TOKENS:
            count = text.count(token)
            if count:
                view_findings.append(f"{run_id}: {token} x{count}")
    transcript_findings: list[str] = []
    audited_transcripts = 0
    transcript_root = arguments.submission_root / V041_TRACKB_SUITE_ID
    for transcript in sorted(transcript_root.rglob("transcript-attempt-*.stream.jsonl")):
        audited_transcripts += 1
        text = transcript.read_text(errors="ignore")
        text = text.replace("/workspaces/epistemic-research-loop/.venv/", "<interpreter-venv>/")
        for token in FORBIDDEN_TOKENS:
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
