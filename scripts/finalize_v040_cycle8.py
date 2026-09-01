#!/usr/bin/env python3
"""Unblind the locked cycle-budget ablation and compare against each configuration's
existing cycle=4 baseline (read from already-published prior-study selection files,
not re-run).

Per docs/v040_cycle_budget_ablation_preregistration.json: K8-opus-P1 compares against
generation 1's C3 + Stage 1's L-opus-P1 (8 pooled cycle=4 replicates); K8-sol-P1
compares against the sol-effort ablation's S-xhigh (6 cycle=4 replicates). Also reports
the named persistent_delayed_history binary endpoint.
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
    V040_CYCLE8_CONFIGS,
    V040_CYCLE8_RUN_IDS,
    V040_CYCLE8_SUITE_IDS,
)
from epistemic_loop.controller.v040_agent import load_v040_submission
from epistemic_loop.evaluation.v038 import evaluate_v038_runs

SELECTION_FAMILY_PREFIXES = ("persistent_", "grammar_composed")

# (config_id in this study) -> baseline description read from already-unblinded prior studies.
_BASELINES: dict[str, dict[str, object]] = {
    "K8-opus-P1": {
        "sources": ["docs/v040_gen1_selection.json:C3", "docs/v040_scaffold_ladder_selection.json:L-opus-P1"],
        "cycle4_replicates": 8,
        "cycle4_discovery_events": 7 + 9,
        # gen1 C3 per-suite semantic_family_count [8,4,4,2] (docs/v040_gen1_diagnostics.json) pooled
        # with Stage 1 L-opus-P1's mean 3.0 over its own 4 replicates: (18 + 12) / 8.
        "cycle4_mean_semantic_family_count": (18 + 12) / 8,
    },
    "K8-sol-P1": {
        "sources": ["docs/v040_sol_ablation_selection.json:S-xhigh"],
        "cycle4_replicates": 6,
        "cycle4_discovery_events": 7,
        "cycle4_mean_semantic_family_count": 1.6666666666666667,
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth-root", type=Path, default=Path(".controller_truth/v040"))
    parser.add_argument("--key-file", type=Path, default=Path(".state/v040/controller.key"))
    parser.add_argument("--submission-root", type=Path, default=Path(".runs/v040/agent_outputs"))
    parser.add_argument("--suite-root", type=Path, default=Path(".runs/v040"))
    parser.add_argument("--output-root", type=Path, default=Path("docs"))
    arguments = parser.parse_args()
    lock = json.loads((arguments.suite_root / "cycle8_agent_runs.lock.json").read_text())
    expected = len(V040_CYCLE8_SUITE_IDS) * len(V040_CYCLE8_RUN_IDS)
    if lock.get("all_outputs_locked_before_hidden_evaluation") is not True or lock.get("agent_run_count") != expected:
        raise SystemExit(f"all {expected} cycle8 outputs must be locked before unblinding")
    _verify_lock(lock, arguments.suite_root, arguments.submission_root)
    key = arguments.key_file.read_bytes().strip()
    truths = tuple(
        decrypt_v037_suite(arguments.truth_root / f"{suite_id}.manifest.enc", key) for suite_id in V040_CYCLE8_SUITE_IDS
    )
    loaded = tuple(
        load_v040_submission(arguments.submission_root / suite_id / run_id / "agent_submission.json")
        for suite_id in V040_CYCLE8_SUITE_IDS
        for run_id in V040_CYCLE8_RUN_IDS
    )
    report = evaluate_v038_runs(
        tuple(item.base for item in loaded),
        truths,
        None,
        expected_suite_count=len(V040_CYCLE8_SUITE_IDS),
    )
    base = report.base
    per_config: dict[str, dict[str, object]] = {}
    for run_id, config in V040_CYCLE8_CONFIGS.items():
        packs = [item for item in base.packs if item.run_id == run_id]
        target = [
            item
            for item in packs
            if item.structure_present and any(item.family.startswith(prefix) for prefix in SELECTION_FAMILY_PREFIXES)
        ]
        discoveries = [item for item in target if item.behaviorally_discovered]
        negatives = [item for item in packs if not item.structure_present]
        cards = [card for card in base.runs if card.run_id == run_id]
        delayed_history = [item for item in packs if item.family == "persistent_delayed_history"]
        config_id = config["config_id"]
        per_config[config_id] = {
            "run_slot": run_id,
            "model": config["model"],
            "prompt_arm": config["prompt_arm"],
            "max_cycles_per_pack": 8,
            "replicates": len({item.suite_id for item in packs}),
            "target_positive_packs": len(target),
            "verified_discovery_events": len(discoveries),
            "discovered_families": sorted({item.family for item in discoveries}),
            "false_promotions": sum(item.false_promotion for item in negatives),
            "evidence_rejections": sum(item.explicitly_rejected for item in negatives),
            "diversity_metrics": {
                "mean_semantic_family_count": fmean(card.semantic_family_count for card in cards),
                "mean_effective_family_count": fmean(card.effective_family_count for card in cards),
                "mean_eecr": fmean(card.eecr for card in cards),
            },
            "persistent_delayed_history_discovered": any(item.behaviorally_discovered for item in delayed_history),
            "persistent_delayed_history_resolutions": sorted(
                f"{item.suite_id}:{item.resolution.value}" for item in delayed_history
            ),
            "cycle4_baseline": _BASELINES.get(config_id, {}),
        }
    arguments.output_root.mkdir(parents=True, exist_ok=True)
    _write(
        arguments.output_root / "v040_cycle8_selection.json",
        {
            "version": "0.4.0",
            "study": "cycle-budget-ablation",
            "per_config": per_config,
            "any_persistent_delayed_history_discovery": any(
                bool(item["persistent_delayed_history_discovered"]) for item in per_config.values()
            ),
        },
    )
    _write(
        arguments.output_root / "v040_cycle8_diagnostics.json",
        {
            "per_run": [asdict(item) for item in base.runs],
            "packs": [asdict(item) for item in base.packs],
            "failure_stage_counts": base.failure_stage_counts,
            "provenance_audit": asdict(report.provenance_audit),
        },
    )
    print(json.dumps({"per_config": per_config}, indent=2))


def _verify_lock(lock: dict[str, object], suite_root: Path, submission_root: Path) -> None:
    records = lock.get("records")
    expected = len(V040_CYCLE8_SUITE_IDS) * len(V040_CYCLE8_RUN_IDS)
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
