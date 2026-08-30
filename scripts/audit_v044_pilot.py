#!/usr/bin/env python3
"""Audit a v0.4.4 pilot's agent-visible view (and transcripts) for blindness leaks.

Same two-surface pattern as scripts/audit_v042_blindness.py, plus this pilot's own
specific risk (see docs/verification/v044_full_feature_pilot_preregistration.md SS3):
the repo's absolute path, reachable via the scorer tool's environment variables if the
agent inspects its own environment (e.g. running `env`) rather than only invoking the
tool as instructed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

_GENERIC_FORBIDDEN_TOKENS = (
    ".controller_truth",
    "controller.key",
    "scorer.key",
    "manifest.enc",
    "labels.enc",
    "/workspaces/epistemic-research-loop",
    "erl-v044-runs",
)

_COMPETITION_FORBIDDEN_TOKENS: dict[str, tuple[str, ...]] = {
    "ieee-cis": (
        "isFraud",
        "TransactionID",
        "TransactionDT",
        "ieee-cis",
        "ieee_cis",
        "IEEE-CIS",
        "Vesta",
        "train_transaction",
        "train_identity",
    ),
    "santander-customer-transaction-prediction": (
        "ID_code",
        "santander",
        "Santander",
        "santander-customer-transaction-prediction",
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--competition-id", required=True, choices=sorted(_COMPETITION_FORBIDDEN_TOKENS))
    parser.add_argument("--suite-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--suite-root", type=Path, default=Path(".runs/v044"))
    parser.add_argument("--submission-root", type=Path, default=Path(".runs/v044/agent_outputs"))
    arguments = parser.parse_args()
    forbidden_tokens = _GENERIC_FORBIDDEN_TOKENS + _COMPETITION_FORBIDDEN_TOKENS[arguments.competition_id]

    view_root = arguments.suite_root / arguments.suite_id / "agent_views" / arguments.run_id
    view_findings: list[str] = []
    if view_root.exists():
        text = "\n".join(path.read_text(errors="ignore") for path in view_root.rglob("*") if path.is_file())
        for token in forbidden_tokens:
            count = text.count(token)
            if count:
                view_findings.append(f"view: {token} x{count}")

    transcript_root = arguments.submission_root / arguments.suite_id / arguments.run_id
    transcript_findings: list[str] = []
    audited_transcripts = 0
    for transcript in sorted(transcript_root.glob("transcript-attempt-*.stream.jsonl")):
        audited_transcripts += 1
        text = transcript.read_text(errors="ignore")
        text = text.replace("/workspaces/epistemic-research-loop/.venv/", "<interpreter-venv>/")
        for token in forbidden_tokens:
            count = text.count(token)
            if count:
                transcript_findings.append(f"{transcript.name}: {token} x{count}")

    payload = {
        "competition_id": arguments.competition_id,
        "suite_id": arguments.suite_id,
        "run_id": arguments.run_id,
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
