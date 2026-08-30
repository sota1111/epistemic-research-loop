#!/usr/bin/env python3
"""Audit a v0.4.4 suite's agent-visible views (and transcripts) for blindness leaks.

Same two-surface pattern as scripts/audit_v042_blindness.py, plus this suite's own
specific risk (see docs/verification/v044_full_feature_pilot_preregistration.md SS3):
the repo's absolute path, reachable via the scorer tool's environment variables if an
agent inspects its own environment (e.g. running `env`) rather than only invoking the
tool as instructed. Iterates every run_id in V044_SOL_EFFORT_CONFIGS, same as
audit_v042_blindness.py does for its suites.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from epistemic_loop.benchmark.v044_full_feature_pilot import V044_SOL_EFFORT_RUN_IDS

_GENERIC_FORBIDDEN_TOKENS = (
    ".controller_truth",
    "controller.key",
    "scorer.key",
    "manifest.enc",
    "labels.enc",
    "/workspaces/epistemic-research-loop",
)
#: NOT forbidden: "erl-v044-runs" (the agent's own workdir-root name) -- by design the
#: agent knows its own cwd (RUNNER.md tells it to work "in this directory"), and that
#: sandbox path reveals nothing about the real repo location, competition identity, or
#: solution content. An earlier version of this list included it and flagged 10 entirely
#: benign occurrences (the agent's own file-write paths) as findings; removed.

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
    parser.add_argument("--suite-root", type=Path, default=Path(".runs/v044"))
    parser.add_argument("--submission-root", type=Path, default=Path(".runs/v044/agent_outputs"))
    arguments = parser.parse_args()
    forbidden_tokens = _GENERIC_FORBIDDEN_TOKENS + _COMPETITION_FORBIDDEN_TOKENS[arguments.competition_id]

    view_findings: list[str] = []
    audited_views = 0
    for run_id in V044_SOL_EFFORT_RUN_IDS:
        view_root = arguments.suite_root / arguments.suite_id / "agent_views" / run_id
        if not view_root.exists():
            continue
        audited_views += 1
        text = "\n".join(path.read_text(errors="ignore") for path in view_root.rglob("*") if path.is_file())
        for token in forbidden_tokens:
            count = text.count(token)
            if count:
                view_findings.append(f"{run_id}: {token} x{count}")

    transcript_findings: list[str] = []
    audited_transcripts = 0
    for run_id in V044_SOL_EFFORT_RUN_IDS:
        transcript_root = arguments.submission_root / arguments.suite_id / run_id
        for transcript in sorted(transcript_root.glob("transcript-attempt-*.stream.jsonl")):
            audited_transcripts += 1
            text = transcript.read_text(errors="ignore")
            text = text.replace("/workspaces/epistemic-research-loop/.venv/", "<interpreter-venv>/")
            for token in forbidden_tokens:
                count = text.count(token)
                if count:
                    transcript_findings.append(f"{run_id}/{transcript.name}: {token} x{count}")

    payload = {
        "competition_id": arguments.competition_id,
        "suite_id": arguments.suite_id,
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
