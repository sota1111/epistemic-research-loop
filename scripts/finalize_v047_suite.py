#!/usr/bin/env python3
"""Score a v0.4.7 suite's local sealed transfer predictions and summarize confirmation usage.

Same mechanism as scripts/finalize_v044_suite.py (independent Controller-side scoring
against the sealed local transfer region, never touched by the agent-invokable scorer
tool). This is the "local proxy score" side of the local-vs-real-leaderboard comparison
docs/c_lite_v047_policy.md SS4 sets up -- it says nothing about the real Kaggle test set
predictions (those are handled by scripts/prepare_kaggle_submission.py).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median

from cryptography.fernet import Fernet

from epistemic_loop.benchmark.v037_repro_suite import _auc
from epistemic_loop.benchmark.v047_kaggle_submission_suite import V047_CANDIDATE_CONFIGS, V047_CANDIDATE_RUN_IDS


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--competition-id", required=True)
    parser.add_argument("--suite-id", required=True)
    parser.add_argument("--truth-root", type=Path, default=Path(".controller_truth/v047"))
    parser.add_argument("--key-file", type=Path, default=Path(".state/v040/controller.key"))
    parser.add_argument("--submission-root", type=Path, default=Path(".runs/v047/agent_outputs"))
    parser.add_argument("--suite-root", type=Path, default=Path(".runs/v047"))
    parser.add_argument("--output", type=Path, default=None)
    arguments = parser.parse_args()
    if arguments.output is None:
        arguments.output = Path(f"docs/v047_{arguments.suite_id.replace('-', '_')}_diagnostics.json")

    key = arguments.key_file.read_bytes().strip()
    transfer_labels_path = arguments.truth_root / f"{arguments.suite_id}_transfer_labels.enc"
    transfer_labels = json.loads(Fernet(key).decrypt(transfer_labels_path.read_bytes()))
    ordered_ids = sorted(transfer_labels, key=int)
    targets = [float(transfer_labels[row_id]) for row_id in ordered_ids]

    lock_file = arguments.suite_root / f"{arguments.suite_id}_suite_lock.json"
    reference_baseline_auc = None
    if lock_file.exists():
        lock_payload = json.loads(lock_file.read_text())
        reference_baseline_auc = lock_payload["suite_build"]["reference_baseline_transfer_auc"]

    per_run: list[dict[str, object]] = []
    for run_id in V047_CANDIDATE_RUN_IDS:
        submission_path = arguments.submission_root / arguments.suite_id / run_id / "agent_submission.json"
        if not submission_path.exists():
            continue
        submission = json.loads(submission_path.read_text())
        submitted = {str(int(item["row_id"])): float(item["prediction"]) for item in submission["transfer_predictions"]}
        missing = set(transfer_labels) - set(submitted)
        if missing:
            per_run.append({"run_id": run_id, "error": f"{len(missing)} transfer row_ids missing"})
            continue
        predictions = [submitted[row_id] for row_id in ordered_ids]
        transfer_auc = _auc(targets, predictions)

        log_path = arguments.truth_root / f"{arguments.suite_id}_{run_id}_call_log.jsonl"
        calls: list[dict[str, object]] = []
        if log_path.exists():
            calls = [json.loads(line) for line in log_path.open() if line.strip()]
        call_aucs = [float(item["auc"]) for item in calls]

        config = V047_CANDIDATE_CONFIGS[run_id]
        per_run.append(
            {
                "run_id": run_id,
                "config_id": config["config_id"],
                "cli": config["cli"],
                "model": config["model"],
                "reasoning_effort": config.get("reasoning_effort"),
                "prompt_arm": config["prompt_arm"],
                "local_transfer_auc": transfer_auc,
                "beats_reference_baseline": (
                    transfer_auc > reference_baseline_auc if reference_baseline_auc is not None else None
                ),
                "self_reported_confirmation_calls": submission.get("confirmation_calls_made"),
                "actual_confirmation_calls": len(calls),
                "confirmation_call_auc_median": median(call_aucs) if call_aucs else None,
                "approach_summary": submission.get("approach_summary"),
                "final_predictions_path": str(
                    arguments.submission_root / arguments.suite_id / run_id / "final_predictions.csv"
                ),
            }
        )

    payload = {
        "version": "0.4.7",
        "study": "v047-kaggle-late-submission-suite",
        "competition_id": arguments.competition_id,
        "suite_id": arguments.suite_id,
        "reference_baseline_transfer_auc": reference_baseline_auc,
        "per_run": per_run,
    }
    arguments.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
