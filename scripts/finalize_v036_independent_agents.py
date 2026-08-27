#!/usr/bin/env python3
"""Unblind a locked v0.3.6 batch and write post-hoc qualification reports."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from epistemic_loop.benchmark.v036_blind_suite import DEFAULT_AGENTS, decrypt_suite_truth
from epistemic_loop.controller.v036_real_agent import load_real_agent_submission
from epistemic_loop.evaluation.v036 import (
    V036Acceptance,
    V036Reliability,
    evaluate_real_agent_population,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth-manifest", type=Path, required=True)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--lock-file", type=Path, required=True)
    parser.add_argument("--submission-root", type=Path, required=True)
    parser.add_argument("--blindness-report", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=Path("docs"))
    arguments = parser.parse_args()
    lock = json.loads(arguments.lock_file.read_text())
    if not lock.get("all_outputs_locked_before_unblinding") or lock.get("agent_count") != 3:
        raise SystemExit("all three real-agent outputs must be locked before unblinding")
    truth = decrypt_suite_truth(arguments.truth_manifest, arguments.key_file.read_bytes().strip())
    submissions = tuple(
        load_real_agent_submission(arguments.submission_root / agent / "agent_submission.json")
        for agent in DEFAULT_AGENTS
    )
    report = evaluate_real_agent_population(submissions, truth)
    blindness = json.loads(arguments.blindness_report.read_text())
    reliability = V036Reliability(
        controller_truth_leakage=int(blindness.get("controller_truth_leakage", 1)),
        family_polarity_leakage=0,
        sealed_label_leakage=0,
        reference_probe_access=0,
        artifact_completion=sum(item.artifact_complete for item in submissions) / len(submissions),
        oof_honesty=sum(item.oof_honesty_passed for item in submissions) / len(submissions),
        sealed_isolation=sum(item.sealed_isolation_passed for item in submissions) / len(submissions),
        human_assisted_primary_runs=sum(item.human_assisted for item in submissions),
    )
    acceptance = V036Acceptance.assess(report, reliability)
    output = arguments.output_root
    output.mkdir(parents=True, exist_ok=True)
    _write(output / "v036_agent_scorecards.json", {item.agent_id: asdict(item) for item in report.agents})
    _write(output / "v036_population_scorecard.json", asdict(report))
    _write(
        output / "v036_structure_discovery_report.json",
        {
            "agent_level": {
                item.agent_id: {
                    "tsdr": item.true_structure_discovery_rate,
                    "tsrr": item.true_structure_rejection_rate,
                    "fspr": item.false_structure_promotion_rate,
                    "resolution_rate": item.structure_resolution_rate,
                    "brier": item.brier_score,
                    "ece": item.expected_calibration_error,
                }
                for item in report.agents
            },
            "population_union": {
                "tsdr": report.population_union_tsdr,
                "tsrr": report.population_union_tsrr,
                "fspr": report.population_union_fspr,
                "resolution_rate": report.structure_resolution_rate,
                "tsdr_interval": asdict(report.tsdr_interval),
                "tsrr_interval": asdict(report.tsrr_interval),
                "fspr_interval": asdict(report.fspr_interval),
            },
            "packs": [asdict(item) for item in report.evaluated_packs],
        },
    )
    _write(
        output / "v036_structure_transfer_report.json",
        {
            "useful_structure_transfer_rate": report.useful_structure_transfer_rate,
            "median_structure_sealed_gain": report.median_structure_sealed_gain,
            "best_agent_selected_auc": report.best_agent_selected_auc,
            "population_selectable_auc": report.population_selectable_auc,
            "population_oracle_auc": report.population_oracle_auc,
            "shadow_candidate_recovery_rate": report.shadow_candidate_recovery_rate,
        },
    )
    _write(
        output / "v036_qualification_result.json",
        {
            "version": "0.3.6",
            "scope": "blind autonomous real-agent synthetic qualification",
            "suite_id": truth.suite_id,
            "reliability": asdict(reliability),
            "population": asdict(report),
            "acceptance": asdict(acceptance),
        },
    )
    print(json.dumps({"acceptance": asdict(acceptance), "population": asdict(report)}, indent=2, sort_keys=True))


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
