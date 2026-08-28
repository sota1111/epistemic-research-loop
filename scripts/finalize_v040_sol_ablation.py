#!/usr/bin/env python3
"""Unblind the locked codex sol reasoning-effort ablation and report per-effort-level results.

Unlike finalize_v040.py's configuration-selection table, this reports discovery events
alongside diversity/exploration-breadth secondary metrics (semantic_family_count,
effective_family_count, eecr, deep_lineage_completion_rate) per reasoning-effort level, per
the ablation's preregistered no-monotonicity-assumed predictions
(docs/v040_sol_effort_ablation_preregistration.json).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from statistics import fmean

from epistemic_loop.benchmark.v037_repro_suite import decrypt_v037_suite
from epistemic_loop.benchmark.v040_grammar_suite import (
    V040_SOL_ABLATION_CONFIGS,
    V040_SOL_ABLATION_RUN_IDS,
    V040_SOL_ABLATION_SUITE_IDS,
)
from epistemic_loop.controller.v040_agent import load_v040_submission
from epistemic_loop.evaluation.v038 import evaluate_v038_runs

SELECTION_FAMILY_PREFIXES = ("persistent_", "grammar_composed")
_EFFORT_ORDER = ("low", "medium", "high", "xhigh")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth-root", type=Path, default=Path(".controller_truth/v040"))
    parser.add_argument("--key-file", type=Path, default=Path(".state/v040/controller.key"))
    parser.add_argument("--submission-root", type=Path, default=Path(".runs/v040/agent_outputs"))
    parser.add_argument("--suite-root", type=Path, default=Path(".runs/v040"))
    parser.add_argument("--output-root", type=Path, default=Path("docs"))
    arguments = parser.parse_args()
    lock = json.loads((arguments.suite_root / "sol_ablation_agent_runs.lock.json").read_text())
    expected = len(V040_SOL_ABLATION_SUITE_IDS) * len(V040_SOL_ABLATION_RUN_IDS)
    if lock.get("all_outputs_locked_before_hidden_evaluation") is not True or lock.get("agent_run_count") != expected:
        raise SystemExit(f"all {expected} sol-ablation outputs must be locked before unblinding")
    _verify_lock(lock, arguments.suite_root, arguments.submission_root)
    key = arguments.key_file.read_bytes().strip()
    truths = tuple(
        decrypt_v037_suite(arguments.truth_root / f"{suite_id}.manifest.enc", key)
        for suite_id in V040_SOL_ABLATION_SUITE_IDS
    )
    loaded = tuple(
        load_v040_submission(arguments.submission_root / suite_id / run_id / "agent_submission.json")
        for suite_id in V040_SOL_ABLATION_SUITE_IDS
        for run_id in V040_SOL_ABLATION_RUN_IDS
    )
    report = evaluate_v038_runs(tuple(item.base for item in loaded), truths, None)
    base = report.base
    per_effort: dict[str, dict[str, object]] = {}
    for run_id, config in V040_SOL_ABLATION_CONFIGS.items():
        packs = [item for item in base.packs if item.run_id == run_id]
        target = [
            item
            for item in packs
            if item.structure_present and any(item.family.startswith(prefix) for prefix in SELECTION_FAMILY_PREFIXES)
        ]
        discoveries = [item for item in target if item.behaviorally_discovered]
        negatives = [item for item in packs if not item.structure_present]
        cards = [card for card in base.runs if card.run_id == run_id]
        per_effort[config["reasoning_effort"]] = {
            "config_id": config["config_id"],
            "run_slot": run_id,
            "replicates": len({item.suite_id for item in packs}),
            "target_positive_packs": len(target),
            "verified_discovery_events": len(discoveries),
            "discovered_families": sorted({item.family for item in discoveries}),
            "false_promotions": sum(item.false_promotion for item in negatives),
            "evidence_rejections": sum(item.explicitly_rejected for item in negatives),
            "all_positive_tsdr": (
                sum(item.behaviorally_discovered for item in packs if item.structure_present)
                / max(1, sum(item.structure_present for item in packs))
            ),
            "diversity_metrics": {
                "mean_semantic_family_count": fmean(card.semantic_family_count for card in cards),
                "mean_effective_family_count": fmean(card.effective_family_count for card in cards),
                "mean_eecr": fmean(card.eecr for card in cards),
                "mean_deep_lineage_completion_rate": fmean(card.deep_lineage_completion_rate for card in cards),
            },
        }
    ordered = {effort: per_effort[effort] for effort in _EFFORT_ORDER if effort in per_effort}
    arguments.output_root.mkdir(parents=True, exist_ok=True)
    _write(
        arguments.output_root / "v040_sol_ablation_selection.json",
        {
            "version": "0.4.0",
            "study": "sol-effort-ablation",
            "per_effort_level": ordered,
            "effort_order": [effort for effort in _EFFORT_ORDER if effort in per_effort],
        },
    )
    _write(
        arguments.output_root / "v040_sol_ablation_diagnostics.json",
        {
            "per_run": [asdict(item) for item in base.runs],
            "packs": [asdict(item) for item in base.packs],
            "failure_stage_counts": base.failure_stage_counts,
            "provenance_audit": asdict(report.provenance_audit),
        },
    )
    print(json.dumps({"per_effort_level": ordered}, indent=2))


def _verify_lock(lock: dict[str, object], suite_root: Path, submission_root: Path) -> None:
    records = lock.get("records")
    expected = len(V040_SOL_ABLATION_SUITE_IDS) * len(V040_SOL_ABLATION_RUN_IDS)
    if not isinstance(records, list) or len(records) != expected:
        raise SystemExit(f"lock must contain {expected} hash records")
    for raw in records:
        if not isinstance(raw, dict):
            raise SystemExit("invalid lock record")
        suite_id = str(raw.get("suite_id"))
        run_id = str(raw.get("run_id"))
        packet = suite_root / suite_id / "agent_views" / run_id / "agent_packet.json"
        submission = submission_root / suite_id / run_id / "agent_submission.json"
        for path, field in ((packet, "packet_sha256"), (submission, "submission_sha256")):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != raw.get(field):
                raise SystemExit(f"locked artifact changed after lock: {suite_id}/{run_id}/{path.name}")


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
