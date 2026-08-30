#!/usr/bin/env python3
"""Audit a v0.4.2 suite's agent-visible views (and transcripts) for blindness leaks.

Same two-surface pattern as every v0.4.0/Track B blindness audit, plus per-competition
identifying tokens (raw column names before hashing, dataset/company names).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from epistemic_loop.benchmark.v037_repro_suite import audit_v037_agent_view
from epistemic_loop.benchmark.v042_multi_competition_suite import (
    V042_RUN_IDS,
    V043_SOL_EFFORT_R2_IEEE_CIS_RUN_IDS,
    V043_SOL_EFFORT_R2_SANTANDER_RUN_IDS,
    V043_SOL_EFFORT_R3_IEEE_CIS_RUN_IDS,
    V043_SOL_EFFORT_R3_SANTANDER_RUN_IDS,
    V043_SOL_EFFORT_RUN_IDS,
)

_RUN_ID_SETS: dict[str, tuple[str, ...]] = {
    "default": V042_RUN_IDS,
    "sol-effort": V043_SOL_EFFORT_RUN_IDS,
    "sol-effort-r2-a": V043_SOL_EFFORT_R2_IEEE_CIS_RUN_IDS,
    "sol-effort-r2-b": V043_SOL_EFFORT_R2_SANTANDER_RUN_IDS,
    "sol-effort-r3-a": V043_SOL_EFFORT_R3_IEEE_CIS_RUN_IDS,
    "sol-effort-r3-b": V043_SOL_EFFORT_R3_SANTANDER_RUN_IDS,
}

_GENERIC_FORBIDDEN_TOKENS = (
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
    parser.add_argument("--config-set", default="default", choices=sorted(_RUN_ID_SETS))
    parser.add_argument("--suite-root", type=Path, default=Path(".runs/v042"))
    parser.add_argument("--submission-root", type=Path, default=Path(".runs/v042/agent_outputs"))
    arguments = parser.parse_args()
    forbidden_tokens = _GENERIC_FORBIDDEN_TOKENS + _COMPETITION_FORBIDDEN_TOKENS[arguments.competition_id]
    view_findings: list[str] = []
    audited_views = 0
    for run_id in _RUN_ID_SETS[arguments.config_set]:
        root = arguments.suite_root / arguments.suite_id / "agent_views" / run_id
        if not root.exists():
            continue
        audited_views += 1
        view_findings.extend(f"{run_id}/{item}" for item in audit_v037_agent_view(root))
        text = "\n".join(path.read_text(errors="ignore") for path in root.rglob("*") if path.is_file())
        for token in forbidden_tokens:
            count = text.count(token)
            if count:
                view_findings.append(f"{run_id}: {token} x{count}")
    transcript_findings: list[str] = []
    audited_transcripts = 0
    transcript_root = arguments.submission_root / arguments.suite_id
    for transcript in sorted(transcript_root.rglob("transcript-attempt-*.stream.jsonl")):
        audited_transcripts += 1
        text = transcript.read_text(errors="ignore")
        text = text.replace("/workspaces/epistemic-research-loop/.venv/", "<interpreter-venv>/")
        for token in forbidden_tokens:
            count = text.count(token)
            if count:
                transcript_findings.append(f"{transcript.relative_to(arguments.submission_root)}: {token} x{count}")
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
