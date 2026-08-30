#!/usr/bin/env python3
"""Score a v0.4.4 suite's final transfer predictions and summarize confirmation usage.

Independent Controller-side scoring against the sealed transfer region (never touched by
the agent-invokable scorer tool -- that only ever sees the confirmation region) for every
run in the suite, plus a summary of each run's confirmation-loop call log. See
docs/verification/v044_full_feature_pilot_preregistration.md SS6 and
docs/c_lite_v044_policy.md.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median

from cryptography.fernet import Fernet

from epistemic_loop.benchmark.v037_repro_suite import _auc
from epistemic_loop.benchmark.v044_full_feature_pilot import (
    V044_R2_CONFIGS,
    V044_R2_RUN_IDS,
    V044_R3_CONFIGS,
    V044_R3_RUN_IDS,
    V044_SOL_EFFORT_CONFIGS,
    V044_SOL_EFFORT_RUN_IDS,
)

_CONFIG_SETS: dict[str, tuple[object, tuple[str, ...]]] = {
    "screening": (V044_SOL_EFFORT_CONFIGS, V044_SOL_EFFORT_RUN_IDS),
    "confirm": (V044_R2_CONFIGS, V044_R2_RUN_IDS),
    "scale": (V044_R3_CONFIGS, V044_R3_RUN_IDS),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--competition-id", required=True)
    parser.add_argument("--suite-id", required=True)
    parser.add_argument("--config-set", default="screening", choices=sorted(_CONFIG_SETS))
    parser.add_argument("--truth-root", type=Path, default=Path(".controller_truth/v044"))
    parser.add_argument("--key-file", type=Path, default=Path(".state/v040/controller.key"))
    parser.add_argument("--submission-root", type=Path, default=Path(".runs/v044/agent_outputs"))
    parser.add_argument("--suite-root", type=Path, default=Path(".runs/v044"))
    parser.add_argument("--output", type=Path, default=None)
    arguments = parser.parse_args()
    if arguments.output is None:
        arguments.output = Path(f"docs/v044_{arguments.suite_id.replace('-', '_')}_diagnostics.json")

    key = arguments.key_file.read_bytes().strip()
    transfer_labels_path = arguments.truth_root / f"{arguments.suite_id}_transfer_labels.enc"
    transfer_labels = json.loads(Fernet(key).decrypt(transfer_labels_path.read_bytes()))
    ordered_ids = sorted(transfer_labels, key=int)
    targets = [float(transfer_labels[row_id]) for row_id in ordered_ids]

    lock_file = arguments.suite_root / f"{arguments.suite_id}_suite_lock.json"
    reference_baseline_auc = None
    if lock_file.exists():
        lock_payload = json.loads(lock_file.read_text())
        reference_baseline_auc = lock_payload["result"]["reference_baseline_transfer_auc"]

    per_run: list[dict[str, object]] = []
    configs, run_ids = _CONFIG_SETS[arguments.config_set]
    for run_id in run_ids:
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

        per_run.append(
            {
                "run_id": run_id,
                "config_id": configs[run_id]["config_id"],
                "reasoning_effort": configs[run_id]["reasoning_effort"],
                "prompt_arm": configs[run_id]["prompt_arm"],
                "transfer_auc": transfer_auc,
                "beats_reference_baseline": (
                    transfer_auc > reference_baseline_auc if reference_baseline_auc is not None else None
                ),
                "self_reported_confirmation_calls": submission.get("confirmation_calls_made"),
                "actual_confirmation_calls": len(calls),
                "confirmation_call_auc_median": median(call_aucs) if call_aucs else None,
                "confirmation_score_trajectory_improved": (
                    call_aucs[-1] > call_aucs[0] if len(call_aucs) >= 2 else None
                ),
                "approach_summary": submission.get("approach_summary"),
            }
        )

    payload = {
        "version": "0.4.4",
        "study": "v044-full-feature-suite",
        "competition_id": arguments.competition_id,
        "suite_id": arguments.suite_id,
        "reference_baseline_transfer_auc": reference_baseline_auc,
        "per_run": per_run,
    }
    arguments.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
