#!/usr/bin/env python3
"""Local pseudo-scoring tool for v0.4.4 pilot agents.

A COPY of this script is placed inside each agent's own working directory by the runner
(so the agent invokes it as ``python3 ./score_confirmation.py ...``, a relative path --
never told the real repo location). It reads two paths from environment variables
(``V044_TRUTH_ROOT``, ``V044_KEY_FILE``) that the runner sets when it spawns the agent
process; those paths point outside the agent's own working directory
(.controller_truth/v044/, .state/v044/ -- see
docs/verification/v044_full_feature_pilot_preregistration.md SS3) and are never written
into any file the agent can read, only injected into its own process environment. This
script decrypts the confirmation region's Fernet-encrypted true labels, computes AUC
against the submitted predictions, and logs the call (outside the agent's reach) for
later audit. Calls per run are capped to discourage using this as a label-extraction
oracle.

This is a local, offline tool -- not network access. It never reveals the competition
identity, dataset name, repo location, or raw labels; it returns only a numeric score.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
from pathlib import Path

from cryptography.fernet import Fernet

_MAX_CALLS = 20


def _auc(targets: list[float], predictions: list[float]) -> float:
    # Duplicated (not imported) deliberately: this file is copied verbatim into each
    # agent's own working directory, so it must have zero imports back into the
    # Controller-only source tree (which would require exposing that tree's path).
    positives = sum(targets)
    negatives = len(targets) - positives
    if not positives or not negatives:
        return 0.5
    ordered = sorted(zip(predictions, targets, strict=True), key=lambda item: item[0])
    rank_sum = 0.0
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and ordered[end][0] == ordered[start][0]:
            end += 1
        rank_sum += (start + 1 + end) / 2 * sum(target for _, target in ordered[start:end])
        start = end
    return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--predictions", required=True, type=Path)
    arguments = parser.parse_args()

    truth_root = Path(os.environ["V044_TRUTH_ROOT"])
    key_file = Path(os.environ["V044_KEY_FILE"])

    log_path = truth_root / f"{arguments.suite_id}_{arguments.run_id}_call_log.jsonl"
    prior_calls = 0
    if log_path.exists():
        prior_calls = sum(1 for _ in log_path.open())
    if prior_calls >= _MAX_CALLS:
        print(json.dumps({"error": f"scorer call limit reached ({_MAX_CALLS})"}))
        raise SystemExit(1)

    labels_path = truth_root / f"{arguments.suite_id}_confirmation_labels.enc"
    if not labels_path.exists() or not key_file.exists():
        print(json.dumps({"error": "no confirmation labels registered for this suite/run"}))
        raise SystemExit(1)
    key = key_file.read_bytes().strip()
    labels = json.loads(Fernet(key).decrypt(labels_path.read_bytes()))

    if not arguments.predictions.exists():
        print(json.dumps({"error": f"predictions file not found: {arguments.predictions}"}))
        raise SystemExit(1)
    with arguments.predictions.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or {"row_id", "prediction"} - set(reader.fieldnames):
            print(json.dumps({"error": "predictions CSV must have header: row_id,prediction"}))
            raise SystemExit(1)
        submitted = {str(int(row["row_id"])): float(row["prediction"]) for row in reader}

    missing = set(labels) - set(submitted)
    if missing:
        print(json.dumps({"error": f"{len(missing)} confirmation row_ids missing from submission"}))
        raise SystemExit(1)

    ordered_ids = sorted(labels, key=int)
    targets = [float(labels[row_id]) for row_id in ordered_ids]
    predictions = [submitted[row_id] for row_id in ordered_ids]
    score = _auc(targets, predictions)

    call_index = prior_calls + 1
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as sink:
        sink.write(
            json.dumps(
                {
                    "call_index": call_index,
                    "timestamp": time.time(),
                    "n_rows": len(ordered_ids),
                    "auc": score,
                }
            )
            + "\n"
        )
    print(
        json.dumps(
            {
                "auc": round(score, 4),
                "n_rows_scored": len(ordered_ids),
                "call_index": call_index,
                "calls_remaining": _MAX_CALLS - call_index,
            }
        )
    )


if __name__ == "__main__":
    main()
