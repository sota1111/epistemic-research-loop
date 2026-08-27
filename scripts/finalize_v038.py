#!/usr/bin/env python3
"""Unblind the locked v0.3.8 qualification batch and write the full report set."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from epistemic_loop.benchmark.v037_repro_suite import decrypt_v037_suite
from epistemic_loop.benchmark.v038_repro_suite import V038_QUAL_SUITE_IDS, V038_RUN_IDS
from epistemic_loop.controller.v038_agent import load_v038_submission
from epistemic_loop.evaluation.calibration_v037 import IsotonicCalibrationMap
from epistemic_loop.evaluation.v038 import assess_v038, evaluate_v038_runs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth-root", type=Path, default=Path(".controller_truth/v038"))
    parser.add_argument("--key-file", type=Path, default=Path(".state/v038/controller.key"))
    parser.add_argument("--submission-root", type=Path, default=Path(".runs/v038/agent_outputs"))
    parser.add_argument("--suite-root", type=Path, default=Path(".runs/v038"))
    parser.add_argument("--calibration-file", type=Path, default=Path(".runs/v038/calibration_c1.json"))
    parser.add_argument("--output-root", type=Path, default=Path("docs"))
    arguments = parser.parse_args()
    lock = json.loads((arguments.suite_root / "qualification_agent_runs.lock.json").read_text())
    if not lock.get("all_outputs_locked_before_hidden_evaluation") or lock.get("agent_run_count") != 24:
        raise SystemExit("all 24 qualification outputs must be locked before v0.3.8 unblinding")
    _verify_lock(lock, arguments.suite_root, arguments.submission_root)
    suite_set_lock = json.loads((arguments.suite_root / "suite_set_lock.json").read_text())
    _verify_suite_set_lock(suite_set_lock, arguments.truth_root)
    key = arguments.key_file.read_bytes().strip()
    truths = tuple(
        decrypt_v037_suite(arguments.truth_root / f"{suite_id}.manifest.enc", key) for suite_id in V038_QUAL_SUITE_IDS
    )
    loaded = tuple(
        load_v038_submission(arguments.submission_root / suite_id / run_id / "agent_submission.json")
        for suite_id in V038_QUAL_SUITE_IDS
        for run_id in V038_RUN_IDS
    )
    calibration_map = _load_calibration(arguments.calibration_file)
    report = evaluate_v038_runs(loaded, truths, calibration_map)
    acceptance = assess_v038(report)
    base = report.base
    arguments.output_root.mkdir(parents=True, exist_ok=True)
    _write(
        arguments.output_root / "v038_agent_reproducibility_scorecards.json",
        {
            "individual_runs": [asdict(item) for item in base.runs],
            "agent_aggregates": [asdict(item) for item in base.agent_aggregates],
            "agent_seed_aggregates": [asdict(item) for item in base.agent_seed_aggregates],
            "agent_structure_calibration": [asdict(item) for item in report.agent_structure_calibration],
        },
    )
    _write(
        arguments.output_root / "v038_population_blind_spot_report.json",
        {
            "population_blocks": [asdict(item) for item in base.population_blocks],
            "mean_pairwise_operator_jaccard": report.mean_pairwise_operator_jaccard,
            "per_agent_distinct_operators": dict(report.per_agent_distinct_operators),
        },
    )
    _write(
        arguments.output_root / "v038_structure_failure_traces.json",
        {
            "failure_stage_counts": base.failure_stage_counts,
            "adjudicated_failure_stage_counts": dict(report.adjudicated_failure_stage_counts),
            "packs": [asdict(item) for item in base.packs],
        },
    )
    _write(arguments.output_root / "v038_full_refit_null_audit.json", asdict(report.provenance_audit))
    _write(
        arguments.output_root / "v038_qualification_result.json",
        {
            "version": "0.3.8",
            "report": _compact(report),
            "acceptance": asdict(acceptance.base),
            "calibrated_median_structure_brier": acceptance.calibrated_median_structure_brier,
            "calibrated_median_structure_ece": acceptance.calibrated_median_structure_ece,
        },
    )
    print(
        json.dumps(
            {"acceptance": asdict(acceptance.base), "summary": _compact(report)},
            indent=2,
            sort_keys=True,
        )
    )


def _compact(report) -> dict[str, object]:  # type: ignore[no-untyped-def]
    base = report.base
    fields = (
        "median_agent_tsdr",
        "median_agent_tsrr",
        "worst_agent_fspr",
        "minimum_leave_one_agent_out_tsrr",
        "median_ustr",
        "overall_ustr",
        "median_structure_gain",
        "shared_blind_spot_rate",
        "median_structure_brier",
        "median_structure_ece",
        "persistent_levels_discovered",
        "persistent_agents_discovering",
        "independent_research_diversity",
        "population_effective_family_count",
        "population_dominant_family_fraction",
        "population_action_types",
        "overall_eecr",
        "overall_deep_lineage_completion_rate",
        "prompt_arm_summary",
        "lineage_policy_summary",
        "failure_stage_counts",
    )
    output: dict[str, object] = {field: getattr(base, field) for field in fields}
    output["tsdr_cluster_interval"] = asdict(report.tsdr_cluster_interval)
    output["tsrr_cluster_interval"] = asdict(report.tsrr_cluster_interval)
    output["fspr_cluster_interval"] = asdict(report.fspr_cluster_interval)
    output["adjudicated_failure_stage_counts"] = dict(report.adjudicated_failure_stage_counts)
    output["mean_pairwise_operator_jaccard"] = report.mean_pairwise_operator_jaccard
    return output


def _load_calibration(path: Path) -> IsotonicCalibrationMap | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text())
    return IsotonicCalibrationMap(
        upper_bounds=tuple(payload["isotonic_map"]["upper_bounds"]),
        calibrated_values=tuple(payload["isotonic_map"]["calibrated_values"]),
        training_samples=int(payload["training_samples"]),
    )


def _verify_lock(lock: dict[str, object], suite_root: Path, submission_root: Path) -> None:
    records = lock.get("records")
    if not isinstance(records, list) or len(records) != 24:
        raise SystemExit("lock must contain 24 hash records")
    expected = {(suite_id, run_id) for suite_id in V038_QUAL_SUITE_IDS for run_id in V038_RUN_IDS}
    actual: set[tuple[str, str]] = set()
    for raw in records:
        if not isinstance(raw, dict):
            raise SystemExit("invalid lock record")
        suite_id = str(raw.get("suite_id"))
        run_id = str(raw.get("run_id"))
        actual.add((suite_id, run_id))
        packet = suite_root / suite_id / "agent_views" / run_id / "agent_packet.json"
        submission = submission_root / suite_id / run_id / "agent_submission.json"
        for path, field in ((packet, "packet_sha256"), (submission, "submission_sha256")):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != raw.get(field):
                raise SystemExit(f"locked artifact changed after lock: {suite_id}/{run_id}/{path.name}")
    if actual != expected:
        raise SystemExit("lock record identities do not match the preregistered 24 runs")


def _verify_suite_set_lock(lock: dict[str, object], truth_root: Path) -> None:
    if lock.get("qualification_suite_ids") != list(V038_QUAL_SUITE_IDS):
        raise SystemExit("suite-set lock does not match the preregistered design")
    prompt_path = Path("prompts/generic_research_agent/v038_p1.md")
    digest = hashlib.sha256(prompt_path.read_bytes()).hexdigest()
    if lock.get("prompt_hashes", {}).get("p1") != digest:
        raise SystemExit("frozen prompt changed after suite generation")
    results = lock.get("results")
    if not isinstance(results, list):
        raise SystemExit("suite-set lock must contain build records")
    for raw in results:
        if not isinstance(raw, dict):
            raise SystemExit("invalid suite-set build record")
        suite_id = str(raw.get("suite_id"))
        encrypted = truth_root / f"{suite_id}.manifest.enc"
        digest = hashlib.sha256(encrypted.read_bytes()).hexdigest()
        if digest != raw.get("encrypted_truth_sha256"):
            raise SystemExit(f"encrypted suite truth changed after generation: {suite_id}")


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
