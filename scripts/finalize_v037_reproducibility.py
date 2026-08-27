#!/usr/bin/env python3
"""Unblind a locked v0.3.7 batch and write individual and blind-spot reports."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from epistemic_loop.benchmark.v037_repro_suite import (
    V037_RUN_IDS,
    V037_SUITE_IDS,
    decrypt_v037_suite,
)
from epistemic_loop.controller.v037_agent import load_v037_submission
from epistemic_loop.evaluation.v037 import V037Acceptance, V037AggregateReport, evaluate_v037_runs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth-root", type=Path, default=Path(".controller_truth/v037"))
    parser.add_argument("--key-file", type=Path, default=Path(".state/v037/controller.key"))
    parser.add_argument("--submission-root", type=Path, default=Path(".runs/v037/agent_outputs"))
    parser.add_argument("--suite-root", type=Path, default=Path(".runs/v037"))
    parser.add_argument("--lock-file", type=Path, default=Path(".runs/v037/all_agent_runs.lock.json"))
    parser.add_argument(
        "--suite-set-lock",
        type=Path,
        default=Path(".runs/v037/primary_suite_set_lock.json"),
    )
    parser.add_argument("--output-root", type=Path, default=Path("docs"))
    arguments = parser.parse_args()
    lock = json.loads(arguments.lock_file.read_text())
    if not lock.get("all_outputs_locked_before_hidden_evaluation") or lock.get("agent_run_count") != 24:
        raise SystemExit("all 24 outputs must be locked before v0.3.7 unblinding")
    _verify_lock(lock, arguments.suite_root, arguments.submission_root)
    suite_set_lock = json.loads(arguments.suite_set_lock.read_text())
    _verify_suite_set_lock(suite_set_lock, arguments.truth_root)
    key = arguments.key_file.read_bytes().strip()
    truths = tuple(
        decrypt_v037_suite(arguments.truth_root / f"{suite_id}.manifest.enc", key) for suite_id in V037_SUITE_IDS
    )
    submissions = tuple(
        load_v037_submission(arguments.submission_root / suite_id / run_id / "agent_submission.json")
        for suite_id in V037_SUITE_IDS
        for run_id in V037_RUN_IDS
    )
    report = evaluate_v037_runs(submissions, truths)
    acceptance = V037Acceptance.assess(report)
    arguments.output_root.mkdir(parents=True, exist_ok=True)
    _write(
        arguments.output_root / "v037_agent_reproducibility_scorecards.json",
        {
            "individual_runs": [asdict(item) for item in report.runs],
            "agent_aggregates": [asdict(item) for item in report.agent_aggregates],
            "agent_seed_aggregates": [asdict(item) for item in report.agent_seed_aggregates],
        },
    )
    _write(
        arguments.output_root / "v037_population_blind_spot_report.json",
        [asdict(item) for item in report.population_blocks],
    )
    _write(
        arguments.output_root / "v037_structure_failure_traces.json",
        {
            "failure_stage_counts": report.failure_stage_counts,
            "packs": [asdict(item) for item in report.packs],
        },
    )
    _write(
        arguments.output_root / "v037_qualification_result.json",
        {"version": "0.3.7", "report": _compact_report(report), "acceptance": asdict(acceptance)},
    )
    _write(arguments.output_root / "v037_full_refit_null_audit.json", _full_refit_audit(report))
    print(json.dumps({"acceptance": asdict(acceptance), "summary": _summary(report)}, indent=2, sort_keys=True))


def _summary(report: V037AggregateReport) -> dict[str, object]:
    fields = (
        "median_agent_tsdr",
        "median_agent_tsrr",
        "worst_agent_fspr",
        "minimum_leave_one_agent_out_tsrr",
        "median_ustr",
        "overall_ustr",
        "median_structure_gain",
        "shared_blind_spot_rate",
        "persistent_levels_discovered",
        "persistent_agents_discovering",
        "independent_research_diversity",
        "population_effective_family_count",
        "population_dominant_family_fraction",
        "population_action_types",
        "overall_eecr",
        "overall_deep_lineage_completion_rate",
    )
    return {field: getattr(report, field) for field in fields}


def _compact_report(report: V037AggregateReport) -> dict[str, object]:
    fields = (
        *_summary(report),
        "median_structure_brier",
        "median_structure_ece",
        "worst_structure_brier",
        "worst_structure_ece",
        "prompt_arm_summary",
        "lineage_policy_summary",
        "failure_stage_counts",
        "tsdr_interval",
        "tsrr_interval",
        "fspr_interval",
    )
    value = asdict(report)
    return {field: value[field] for field in fields}


def _full_refit_audit(report: V037AggregateReport) -> dict[str, object]:
    packs = report.packs
    reported = sum(item.full_refit_null for item in packs)
    return {
        "pack_count": len(packs),
        "reported_full_refit_count": reported,
        "reported_full_refit_rate": reported / len(packs),
        "minimum_null_replicates": min(item.null_replicates for item in packs),
        "maximum_null_replicates": max(item.null_replicates for item in packs),
        "per_replicate_fit_fingerprint_available": False,
        "provenance_status": "PARTIAL",
        "interpretation": (
            "The locked contract records full feature regeneration and model refit for every null, "
            "but v0.3.7 did not persist per-replicate source/model/feature fingerprints."
        ),
    }


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _verify_lock(lock: dict[str, object], suite_root: Path, submission_root: Path) -> None:
    records = lock.get("records")
    if not isinstance(records, list) or len(records) != 24:
        raise SystemExit("lock must contain 24 hash records")
    expected = {(suite_id, run_id) for suite_id in V037_SUITE_IDS for run_id in V037_RUN_IDS}
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
    if lock.get("suite_ids") != list(V037_SUITE_IDS) or lock.get("total_agent_runs") != 24:
        raise SystemExit("suite-set lock does not match the preregistered design")
    prompt_paths = {
        "p0": Path("prompts/generic_research_agent/v037_p0.md"),
        "p1": Path("prompts/generic_research_agent/v037_p1.md"),
    }
    prompt_hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in prompt_paths.items()}
    if prompt_hashes != lock.get("prompt_hashes"):
        raise SystemExit("frozen prompt changed after suite generation")
    results = lock.get("results")
    if not isinstance(results, list) or len(results) != len(V037_SUITE_IDS):
        raise SystemExit("suite-set lock must contain four build records")
    for raw in results:
        if not isinstance(raw, dict):
            raise SystemExit("invalid suite-set build record")
        suite_id = str(raw.get("suite_id"))
        encrypted = truth_root / f"{suite_id}.manifest.enc"
        digest = hashlib.sha256(encrypted.read_bytes()).hexdigest()
        if digest != raw.get("encrypted_truth_sha256"):
            raise SystemExit(f"encrypted suite truth changed after generation: {suite_id}")


if __name__ == "__main__":
    main()
