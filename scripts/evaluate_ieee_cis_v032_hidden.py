#!/usr/bin/env python3
"""Submit and collect only an already frozen v0.3.2 hidden batch."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from epistemic_loop.evaluation.primary_endpoint import FrozenSubmissionBatch, spearman_rank_consistency

COMPETITION = "ieee-fraud-detection"


def _command(*arguments: str) -> str:
    process = subprocess.run(arguments, capture_output=True, text=True, check=False)
    if process.returncode != 0:
        raise RuntimeError(process.stderr.strip() or process.stdout.strip())
    return process.stdout


def _submissions() -> list[dict[str, Any]]:
    value = json.loads(
        _command(
            "kaggle",
            "competitions",
            "submissions",
            COMPETITION,
            "--format",
            "json",
            "--page-size",
            "200",
        )
    )
    if not isinstance(value, list):
        raise TypeError("Kaggle submissions response must be a list")
    return [item for item in value if isinstance(item, dict)]


def _optional_float(value: object) -> float | None:
    return None if value in (None, "") else float(str(value))


def collect(batch: FrozenSubmissionBatch, submission_error: str | None = None) -> dict[str, Any]:
    by_description = {str(item.get("description")): item for item in _submissions()}
    observations: list[dict[str, Any]] = []
    for spec in batch.submissions:
        item = by_description.get(spec.kaggle_description)
        observations.append(
            {
                "submission_id": spec.submission_id,
                "description": spec.kaggle_description,
                "local_forward_auc": spec.local_forward_auc,
                "local_protocol": spec.local_protocol,
                "kaggle_ref": item.get("ref") if item else None,
                "status": item.get("status") if item else "PENDING_EXTERNAL_QUOTA",
                "public_auc": _optional_float(item.get("publicScore")) if item else None,
                "private_auc": _optional_float(item.get("privateScore")) if item else None,
            }
        )
    by_id = {item["submission_id"]: item for item in observations}
    archive = by_id["archive_best_single"]["private_auc"]
    single = by_id["workstream_02_single"]["private_auc"]
    ensemble = by_id["archive_plus_workstream_02_nested_ensemble"]["private_auc"]
    deltas = {
        "single_private_gain": single - archive if single is not None and archive is not None else None,
        "ensemble_private_gain": ensemble - archive if ensemble is not None and archive is not None else None,
    }
    private_scores = [item["private_auc"] for item in observations]
    complete = all(value is not None for value in private_scores)
    return {
        "version": "0.3.2",
        "competition": COMPETITION,
        "batch_sha256": batch.batch_sha256,
        "late_submission_endpoint_only": True,
        "official_competition_rank_or_prize_claimed": False,
        "observations": observations,
        "private_deltas": deltas,
        "hidden_transfer_complete": complete,
        "local_to_private_spearman": (
            spearman_rank_consistency(
                [item["local_forward_auc"] for item in observations],
                [float(value) for value in private_scores],
            )
            if complete
            else None
        ),
        "submission_error": submission_error,
        "adaptive_candidate_addition_performed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--submit", action="store_true")
    arguments = parser.parse_args()
    root = arguments.repository_root.resolve()
    manifest = arguments.manifest.resolve()
    batch = FrozenSubmissionBatch.from_path(manifest)
    invalid = {name: result.errors for name, result in batch.verify(root).items() if not result.valid}
    if invalid:
        raise ValueError(f"frozen v0.3.2 artifact changed: {invalid}")
    preregistration = json.loads((manifest.parent / "preregistration.json").read_text(encoding="utf-8"))
    if preregistration["submission_order"] != [item.submission_id for item in batch.submissions]:
        raise ValueError("extended preregistration order differs from frozen submission batch")

    submission_error: str | None = None
    if arguments.submit:
        existing = {str(item.get("description")) for item in _submissions()}
        for spec in batch.submissions:
            if spec.kaggle_description in existing:
                continue
            try:
                _command(
                    "kaggle",
                    "competitions",
                    "submit",
                    "-f",
                    str(root / spec.path),
                    "-m",
                    spec.kaggle_description,
                    COMPETITION,
                )
            except RuntimeError as error:
                submission_error = str(error)
                break
    report = collect(batch, submission_error)
    destination = manifest.parent / "primary_endpoint_results.json"
    destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
