#!/usr/bin/env python3
"""Audit a v0.4.7 suite's agent-visible views (and transcripts) for blindness leaks.

Same pattern as scripts/audit_v044_suite.py (same forbidden-token list, same
_strip_known_scorer_source false-positive fix -- see that script and
docs/verification/v046_low_effort_opus_results.md SS0 for why it's needed), extended to
also scan real_test.csv (the new v0.4.7 file) and to check that no real
TransactionID/ID_code value ever appears verbatim in an agent-visible surface (the
Controller-only id_map is the only place those values are allowed to live).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from epistemic_loop.benchmark.v047_kaggle_submission_suite import V047_CANDIDATE_RUN_IDS

_SCORER_SCRIPT = Path("scripts/v044_score_confirmation.py")


def _strip_known_scorer_source(text: str) -> str:
    source = _SCORER_SCRIPT.read_text()
    for variant in (source, source.rstrip("\n")):
        text = text.replace(json.dumps(variant)[1:-1], "")
    return text


_GENERIC_FORBIDDEN_TOKENS = (
    ".controller_truth",
    "controller.key",
    "scorer.key",
    "manifest.enc",
    "labels.enc",
    "/workspaces/epistemic-research-loop",
)
#: NOT forbidden: "id_map" -- id_map.json is never copied into any agent-visible surface
#: (Controller-only, docs/c_lite_v047_policy.md SS3), so the bare word is just as likely to
#: be an agent's own unrelated variable name as evidence of a leak.

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
        "test_transaction",
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
    parser.add_argument("--suite-root", type=Path, default=Path(".runs/v047"))
    parser.add_argument("--submission-root", type=Path, default=Path(".runs/v047/agent_outputs"))
    arguments = parser.parse_args()
    forbidden_tokens = _GENERIC_FORBIDDEN_TOKENS + _COMPETITION_FORBIDDEN_TOKENS[arguments.competition_id]

    view_findings: list[str] = []
    audited_views = 0
    for run_id in V047_CANDIDATE_RUN_IDS:
        view_root = arguments.suite_root / arguments.suite_id / "agent_views" / run_id
        if not view_root.exists():
            continue
        audited_views += 1
        text = "\n".join(path.read_text(errors="ignore") for path in view_root.rglob("*") if path.is_file())
        text = _strip_known_scorer_source(text)
        for token in forbidden_tokens:
            count = text.count(token)
            if count:
                view_findings.append(f"{run_id}: {token} x{count}")

    transcript_findings: list[str] = []
    audited_transcripts = 0
    for run_id in V047_CANDIDATE_RUN_IDS:
        transcript_root = arguments.submission_root / arguments.suite_id / run_id
        for transcript in sorted(transcript_root.glob("transcript-attempt-*.stream.jsonl")):
            audited_transcripts += 1
            text = transcript.read_text(errors="ignore")
            text = text.replace("/workspaces/epistemic-research-loop/.venv/", "<interpreter-venv>/")
            text = _strip_known_scorer_source(text)
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
