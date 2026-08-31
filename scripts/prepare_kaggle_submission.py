#!/usr/bin/env python3
"""Build a real, Kaggle-submittable submission.csv from one v0.4.7 run's output.

Reads final_predictions.csv (row_id,prediction over the anonymized real_test.csv) and the
Controller-only id_map.json (row_id -> real TransactionID/ID_code,
docs/c_lite_v047_policy.md SS3) produced at build time, and re-attaches the real ids to
build a file with the exact schema of the competition's sample_submission.csv. Validates
row count and id-set equality against sample_submission.csv before writing -- a malformed
file here would either fail Kaggle's own validation or, worse, silently score against the
wrong rows.

This script never calls the Kaggle API itself -- see scripts/submit_kaggle.py for the
actual submission step, which is deliberately kept separate and is not invoked
automatically (docs/c_lite_v047_policy.md SS6/SS7: the first real submission needs
explicit user confirmation).
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from epistemic_loop.benchmark.v047_kaggle_submission_suite import V047_TEST_DATA_PATHS

#: The real Kaggle competition ref (as used by `kaggle competitions submit -c <ref>`) for
#: each of this project's internal competition_id values. NOTE: IEEE-CIS's real Kaggle
#: slug is "ieee-fraud-detection", NOT "ieee-cis-fraud-detection" -- confirmed via
#: `kaggle competitions list -s ieee-cis-fraud-detection` returning nothing and
#: `kaggle competitions submissions ieee-fraud-detection` returning this project's own
#: real submission history (docs/c_lite_v047_policy.md SS0).
V047_KAGGLE_REFS: dict[str, str] = {
    "ieee-cis": "ieee-fraud-detection",
    "santander-customer-transaction-prediction": "santander-customer-transaction-prediction",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--competition-id", required=True, choices=sorted(V047_TEST_DATA_PATHS))
    parser.add_argument("--suite-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--final-predictions", type=Path, default=None)
    parser.add_argument("--id-map-root", type=Path, default=Path(".controller_truth/v047_id_maps"))
    parser.add_argument("--output", type=Path, default=None)
    arguments = parser.parse_args()

    if arguments.final_predictions is None:
        arguments.final_predictions = (
            Path(".runs/v047/agent_outputs") / arguments.suite_id / arguments.run_id / "final_predictions.csv"
        )
    if arguments.output is None:
        arguments.output = Path(".runs/v047/submissions") / f"{arguments.suite_id}_{arguments.run_id}_submission.csv"

    id_map_path = arguments.id_map_root / f"{arguments.suite_id}_{arguments.run_id}_id_map.json"
    id_map_payload = json.loads(id_map_path.read_text())
    id_column = id_map_payload["id_column"]
    id_map = id_map_payload["map"]

    sample_path = V047_TEST_DATA_PATHS[arguments.competition_id].parent / "sample_submission.csv"
    with sample_path.open(newline="") as handle:
        sample_reader = csv.DictReader(handle)
        sample_fieldnames = sample_reader.fieldnames
        if sample_fieldnames is None:
            raise SystemExit(f"could not read header from {sample_path}")
        sample_ids = [row[id_column] for row in sample_reader]
    target_column = [name for name in sample_fieldnames if name != id_column][0]

    with arguments.final_predictions.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or {"row_id", "prediction"} - set(reader.fieldnames):
            raise SystemExit("final_predictions.csv must have header: row_id,prediction")
        predictions_by_row_id = {row["row_id"]: row["prediction"] for row in reader}

    real_id_to_prediction: dict[str, str] = {}
    for row_id, prediction in predictions_by_row_id.items():
        real_id = id_map.get(row_id)
        if real_id is None:
            raise SystemExit(f"row_id {row_id} in final_predictions.csv has no entry in id_map")
        real_id_to_prediction[str(real_id)] = prediction

    missing_ids = set(sample_ids) - set(real_id_to_prediction)
    if missing_ids:
        raise SystemExit(f"{len(missing_ids)} real ids have no prediction (e.g. {next(iter(missing_ids))})")
    extra_ids = set(real_id_to_prediction) - set(sample_ids)
    if extra_ids:
        raise SystemExit(
            f"{len(extra_ids)} predicted ids are not in sample_submission.csv (e.g. {next(iter(extra_ids))})"
        )

    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    with arguments.output.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([id_column, target_column])
        for real_id in sample_ids:
            writer.writerow([real_id, real_id_to_prediction[real_id]])

    print(
        json.dumps(
            {
                "ok": True,
                "output": str(arguments.output),
                "rows": len(sample_ids),
                "kaggle_ref": V047_KAGGLE_REFS[arguments.competition_id],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
