#!/usr/bin/env python3
"""Freeze, submit, and collect the preregistered IEEE-CIS v0.3.1 endpoint batch.

Freeze and submission are deliberately separate.  ``--submit`` accepts only an
already frozen, hash-valid manifest; scores can therefore never change the
candidate set or its order.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from pathlib import Path
from typing import Any

from epistemic_loop.evaluation.primary_endpoint import (
    FrozenSubmissionBatch,
    FrozenSubmissionSpec,
    freeze_submission_batch,
    leaderboard_rank_equivalent,
    rank_values,
    spearman_rank_consistency,
)

DEFAULT_ROOT = Path(".runs/ieee-cis-v031-primary-endpoint")
DEFAULT_MANIFEST = DEFAULT_ROOT / "frozen_batch.json"
COMPETITION = "ieee-fraud-detection"

PREREGISTERED_SUBMISSIONS = (
    FrozenSubmissionSpec(
        submission_id="canonical_baseline",
        path=".results/ieee-epistemic-001/E-SUB-09/submission.csv",
        expected_sha256="d852e19a8fe58cb991a9a9adb3a5d60ee00cc96d065108aba6d29e287168af9c",
        purpose="canonical baseline",
        local_forward_auc=0.9100926867546033,
        local_protocol="group_time_forward_full_train",
        kaggle_description="ERL v031 frozen 01 canonical baseline",
    ),
    FrozenSubmissionSpec(
        submission_id="v02_corrected_locked_ensemble",
        path=".runs/ieee-cis-v02-multi-island-20260826/final-corrected/locked/submission.csv",
        expected_sha256="0f28e8d94d5c2e2c0c7131358a39275a65fe795ad6a9da07c0f7238002b58cf2",
        purpose="v0.2 fixed-niche corrected locked ensemble",
        local_forward_auc=0.948746,
        local_protocol="second_level_common_oof_intersection_1084_rows",
        kaggle_description="ERL v031 frozen 02 v02 corrected locked",
    ),
    FrozenSubmissionSpec(
        submission_id="v03_cycle1_locked_0102_blend",
        path=".runs/ieee-cis-v03-multi-island-20260826-final/locked_submission.csv",
        expected_sha256="86634793e066bc42f788397d145fe5812e3372d71a6abe8d8c32fadf9f34f741",
        purpose="v0.3 cycle-1 locked Island 01/02 blend",
        local_forward_auc=0.873771784,
        local_protocol="second_level_common_oof_intersection_12535_rows",
        kaggle_description="ERL v031 frozen 03 v03 cycle1 0102 blend",
    ),
    FrozenSubmissionSpec(
        submission_id="v03_cycle4_locked_island01",
        path=".runs/ieee-cis-v03-adaptive-cycles-final-20260826/locked_submission.csv",
        expected_sha256="a54764932987eeb58e42bce611bcd0096dc37198b87e636513bfe406fbaa4ee2",
        purpose="v0.3 adaptive cycles 2-4 locked Island 01",
        local_forward_auc=0.869651898,
        local_protocol="second_level_common_oof_intersection_6628_rows",
        kaggle_description="ERL v031 frozen 04 v03 cycle4 island01",
    ),
)


def _command(*arguments: str) -> str:
    process = subprocess.run(arguments, capture_output=True, text=True, check=False)
    if process.returncode != 0:
        raise RuntimeError(process.stderr.strip() or process.stdout.strip())
    return process.stdout


def _submissions() -> list[dict[str, Any]]:
    raw = _command(
        "kaggle",
        "competitions",
        "submissions",
        COMPETITION,
        "--format",
        "json",
        "--page-size",
        "200",
    )
    value = json.loads(raw)
    if not isinstance(value, list):
        raise ValueError("Kaggle submissions response must be a list")
    return [item for item in value if isinstance(item, dict)]


def _leaderboard_scores(path: Path | None) -> tuple[float, ...]:
    if path is None:
        return ()
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return tuple(float(row["Score"]) for row in csv.DictReader(stream))


def _collect(batch: FrozenSubmissionBatch, *, public_leaderboard: Path | None = None) -> dict[str, Any]:
    by_description = {str(item.get("description")): item for item in _submissions()}
    public_scores = _leaderboard_scores(public_leaderboard)
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
                "status": item.get("status") if item else "NOT_SUBMITTED",
                "public_auc": _optional_float(item.get("publicScore")) if item else None,
                "private_auc": _optional_float(item.get("privateScore")) if item else None,
                "public_rank_equivalent": (
                    leaderboard_rank_equivalent(float(item["publicScore"]), public_scores)
                    if item and item.get("publicScore") not in (None, "") and public_scores
                    else None
                ),
                "private_rank_equivalent": None,
            }
        )
    complete = all(item["private_auc"] is not None for item in observations)
    if complete:
        local = [float(item["local_forward_auc"]) for item in observations]
        public = [float(item["public_auc"]) for item in observations]
        private = [float(item["private_auc"]) for item in observations]
        for item, public_rank, private_rank in zip(
            observations, rank_values(public), rank_values(private), strict=True
        ):
            item["public_rank_within_frozen_batch"] = public_rank
            item["private_rank_within_frozen_batch"] = private_rank
        consistency = spearman_rank_consistency(local, private)
    else:
        consistency = None
    return {
        "competition": COMPETITION,
        "batch_sha256": batch.batch_sha256,
        "late_submission_endpoint_only": True,
        "official_competition_rank_or_prize_claimed": False,
        "private_rank_equivalent_status": "unavailable_from_kaggle_public_leaderboard_export",
        "observations": observations,
        "local_to_private_spearman": consistency,
        "comparison_limitations": [
            "Candidate sample sizes and exploration budgets differ.",
            "Local forward protocols are not common first-level cross-fit metrics.",
            "Late scores are post-hoc hidden/private endpoints, not official competition results.",
        ],
    }


def _optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    return float(str(value))


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--collect-only", action="store_true")
    parser.add_argument("--public-leaderboard-csv", type=Path)
    args = parser.parse_args()
    repository_root = args.repository_root.resolve()
    manifest = args.manifest if args.manifest.is_absolute() else repository_root / args.manifest

    if not manifest.exists():
        if args.submit or args.collect_only:
            raise FileNotFoundError("freeze the endpoint batch before submitting or collecting")
        batch = freeze_submission_batch(
            repository_root=repository_root,
            competition=COMPETITION,
            submissions=PREREGISTERED_SUBMISSIONS,
            output_path=manifest,
        )
    else:
        batch = FrozenSubmissionBatch.from_path(manifest)
        if batch.submissions != PREREGISTERED_SUBMISSIONS:
            raise ValueError("the existing frozen batch differs from the preregistered v0.3.1 batch")

    invalid = {name: result.errors for name, result in batch.verify(repository_root).items() if not result.valid}
    if invalid:
        raise ValueError(f"frozen artifacts changed after preregistration: {invalid}")

    if args.submit:
        existing = {str(item.get("description")) for item in _submissions()}
        for spec in batch.submissions:
            if spec.kaggle_description in existing:
                continue
            _command(
                "kaggle",
                "competitions",
                "submit",
                "-f",
                str(repository_root / spec.path),
                "-m",
                spec.kaggle_description,
                COMPETITION,
            )
    leaderboard = args.public_leaderboard_csv
    if leaderboard is not None and not leaderboard.is_absolute():
        leaderboard = repository_root / leaderboard
    report = _collect(batch, public_leaderboard=leaderboard)
    _write_json(manifest.parent / "primary_endpoint_results.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
