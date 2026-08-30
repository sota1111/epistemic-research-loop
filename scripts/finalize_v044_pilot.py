#!/usr/bin/env python3
"""Score a v0.4.4 pilot's final transfer predictions and summarize confirmation usage.

Independent Controller-side scoring against the sealed transfer region (never touched by
the agent-invokable scorer tool -- that only ever sees the confirmation region), plus a
summary of the confirmation-loop call log (how many times the agent called the local
scoring tool, and how the score moved across calls). See
docs/verification/v044_full_feature_pilot_preregistration.md SS6.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median

from cryptography.fernet import Fernet

from epistemic_loop.benchmark.v037_repro_suite import _auc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--truth-root", type=Path, default=Path(".controller_truth/v044"))
    parser.add_argument("--key-file", type=Path, default=Path(".state/v040/controller.key"))
    parser.add_argument("--submission-root", type=Path, default=Path(".runs/v044/agent_outputs"))
    parser.add_argument("--suite-root", type=Path, default=Path(".runs/v044"))
    parser.add_argument("--output", type=Path, default=None)
    arguments = parser.parse_args()
    if arguments.output is None:
        arguments.output = Path(f"docs/v044_{arguments.suite_id.replace('-', '_')}_{arguments.run_id}_diagnostics.json")

    submission_path = arguments.submission_root / arguments.suite_id / arguments.run_id / "agent_submission.json"
    submission = json.loads(submission_path.read_text())

    transfer_labels_path = arguments.truth_root / f"{arguments.suite_id}_{arguments.run_id}_transfer_labels.enc"
    key = arguments.key_file.read_bytes().strip()
    transfer_labels = json.loads(Fernet(key).decrypt(transfer_labels_path.read_bytes()))

    submitted = {str(int(item["row_id"])): float(item["prediction"]) for item in submission["transfer_predictions"]}
    missing = set(transfer_labels) - set(submitted)
    if missing:
        raise SystemExit(f"{len(missing)} transfer row_ids missing from final submission")
    ordered_ids = sorted(transfer_labels, key=int)
    targets = [float(transfer_labels[row_id]) for row_id in ordered_ids]
    predictions = [submitted[row_id] for row_id in ordered_ids]
    transfer_auc = _auc(targets, predictions)

    lock_file = arguments.suite_root / f"{arguments.suite_id}_suite_lock.json"
    reference_baseline_auc = None
    if lock_file.exists():
        lock_payload = json.loads(lock_file.read_text())
        reference_baseline_auc = lock_payload["result"]["reference_baseline_transfer_auc"]

    log_path = arguments.truth_root / f"{arguments.suite_id}_{arguments.run_id}_call_log.jsonl"
    calls: list[dict[str, object]] = []
    if log_path.exists():
        calls = [json.loads(line) for line in log_path.open() if line.strip()]
    call_aucs = [float(item["auc"]) for item in calls]

    payload = {
        "version": "0.4.4",
        "study": "v044-full-feature-pilot",
        "suite_id": arguments.suite_id,
        "run_id": arguments.run_id,
        "transfer_auc": transfer_auc,
        "reference_baseline_transfer_auc": reference_baseline_auc,
        "beats_reference_baseline": (
            transfer_auc > reference_baseline_auc if reference_baseline_auc is not None else None
        ),
        "self_reported_confirmation_calls": submission.get("confirmation_calls_made"),
        "actual_confirmation_calls": len(calls),
        "confirmation_call_aucs": call_aucs,
        "confirmation_call_auc_median": median(call_aucs) if call_aucs else None,
        "confirmation_score_trajectory_improved": (call_aucs[-1] > call_aucs[0] if len(call_aucs) >= 2 else None),
        "approach_summary": submission.get("approach_summary"),
    }
    arguments.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
