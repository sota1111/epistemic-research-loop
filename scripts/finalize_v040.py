#!/usr/bin/env python3
"""Unblind the locked v0.4.0 generation-1 batch: evaluation plus configuration selection.

The primary output is the per-configuration selection table required by the v0.4.0
policy: verified discovery events on persistent and grammar families (with the
matched-negative gate applied) per execution configuration, across the four suites.
The full v0.3.x-compatible evaluation report is written alongside as diagnostics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from epistemic_loop.benchmark.v037_repro_suite import decrypt_v037_suite
from epistemic_loop.benchmark.v040_grammar_suite import (
    V040_GEN1_CONFIGS,
    V040_GEN1_EXCLUDED_RUNS,
    V040_GEN1_SUITE_IDS,
    V040_RUN_IDS,
)
from epistemic_loop.controller.v040_agent import load_v040_submission
from epistemic_loop.evaluation.v038 import evaluate_v038_runs

SELECTION_FAMILY_PREFIXES = ("persistent_", "grammar_composed")

_EXECUTED_PAIRS = [
    (suite, run) for suite in V040_GEN1_SUITE_IDS for run in V040_RUN_IDS if (suite, run) not in V040_GEN1_EXCLUDED_RUNS
]
_EXPECTED_RUN_COUNT = len(_EXECUTED_PAIRS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth-root", type=Path, default=Path(".controller_truth/v040"))
    parser.add_argument("--key-file", type=Path, default=Path(".state/v040/controller.key"))
    parser.add_argument("--submission-root", type=Path, default=Path(".runs/v040/agent_outputs"))
    parser.add_argument("--suite-root", type=Path, default=Path(".runs/v040"))
    parser.add_argument("--output-root", type=Path, default=Path("docs"))
    arguments = parser.parse_args()
    lock = json.loads((arguments.suite_root / "qualification_agent_runs.lock.json").read_text())
    locked_all = lock.get("all_outputs_locked_before_hidden_evaluation")
    if locked_all is not True or lock.get("agent_run_count") != _EXPECTED_RUN_COUNT:
        raise SystemExit(
            f"all {_EXPECTED_RUN_COUNT} executed generation-1 outputs must be locked before v0.4.0 unblinding"
        )
    _verify_lock(lock, arguments.suite_root, arguments.submission_root)
    key = arguments.key_file.read_bytes().strip()
    truths = tuple(
        decrypt_v037_suite(arguments.truth_root / f"{suite_id}.manifest.enc", key) for suite_id in V040_GEN1_SUITE_IDS
    )
    loaded = tuple(
        load_v040_submission(arguments.submission_root / suite_id / run_id / "agent_submission.json")
        for suite_id, run_id in _EXECUTED_PAIRS
    )
    report = evaluate_v038_runs(
        tuple(item.base for item in loaded),
        truths,
        None,
        excluded_pairs=frozenset(V040_GEN1_EXCLUDED_RUNS),
    )
    base = report.base
    selection: dict[str, dict[str, object]] = {}
    for run_id, config in V040_GEN1_CONFIGS.items():
        packs = [item for item in base.packs if item.run_id == run_id]
        target = [
            item
            for item in packs
            if item.structure_present and any(item.family.startswith(prefix) for prefix in SELECTION_FAMILY_PREFIXES)
        ]
        discoveries = [item for item in target if item.behaviorally_discovered]
        negatives = [item for item in packs if not item.structure_present]
        selection[config["config_id"]] = {
            "run_slot": run_id,
            "cli": config["cli"],
            "model": config["model"],
            "prompt_arm": config["prompt_arm"],
            "replicates": len({item.suite_id for item in packs}),
            "target_positive_packs": len(target),
            "verified_discovery_events": len(discoveries),
            "discovered_families": sorted({item.family for item in discoveries}),
            "discovery_suites": sorted({item.suite_id for item in discoveries}),
            "false_promotions": sum(item.false_promotion for item in negatives),
            "evidence_rejections": sum(item.explicitly_rejected for item in negatives),
            "all_positive_tsdr": (
                sum(item.behaviorally_discovered for item in packs if item.structure_present)
                / max(1, sum(item.structure_present for item in packs))
            ),
        }
    ranking = sorted(
        selection.items(),
        key=lambda item: (
            -int(item[1]["verified_discovery_events"]),
            int(item[1]["false_promotions"]),
        ),
    )
    arguments.output_root.mkdir(parents=True, exist_ok=True)
    _write(
        arguments.output_root / "v040_gen1_selection.json",
        {
            "version": "0.4.0",
            "generation": 1,
            "selection_metric": "verified discovery events on persistent/grammar families "
            "(matched-negative gate applied), tie-broken by fewer false promotions",
            "excluded_runs": {f"{suite}/{run}": reason for (suite, run), reason in V040_GEN1_EXCLUDED_RUNS.items()},
            "configurations": selection,
            "ranking": [config_id for config_id, _ in ranking],
        },
    )
    _write(
        arguments.output_root / "v040_gen1_diagnostics.json",
        {
            "per_run": [asdict(item) for item in base.runs],
            "per_config_aggregates": [asdict(item) for item in base.agent_seed_aggregates],
            "packs": [asdict(item) for item in base.packs],
            "failure_stage_counts": base.failure_stage_counts,
            "population_blocks": [asdict(item) for item in base.population_blocks],
            "provenance_audit": asdict(report.provenance_audit),
        },
    )
    print(json.dumps({"ranking": [config_id for config_id, _ in ranking], "selection": selection}, indent=2))


def _verify_lock(lock: dict[str, object], suite_root: Path, submission_root: Path) -> None:
    records = lock.get("records")
    if not isinstance(records, list) or len(records) != _EXPECTED_RUN_COUNT:
        raise SystemExit(f"lock must contain {_EXPECTED_RUN_COUNT} hash records")
    excluded = {f"{suite}/{run}" for suite, run in V040_GEN1_EXCLUDED_RUNS}
    for raw in records:
        if not isinstance(raw, dict):
            raise SystemExit("invalid lock record")
        if f"{raw.get('suite_id')}/{raw.get('run_id')}" in excluded:
            raise SystemExit("lock contains a preregistered-excluded run")
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
