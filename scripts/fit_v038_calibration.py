#!/usr/bin/env python3
"""Fit the development-only C1 isotonic calibration map after the development lock.

Development suite truth is opened here and only here; qualification truth is never
used for fitting. The resulting map and per-agent development ECE (which selects the
C2 evidence gate) are hash-locked before any qualification run is unblinded.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from epistemic_loop.benchmark.v037_repro_suite import decrypt_v037_suite
from epistemic_loop.benchmark.v038_repro_suite import V038_DEV_EXECUTED_RUN_IDS, V038_DEV_SUITE_IDS
from epistemic_loop.controller.v038_agent import load_v038_submission
from epistemic_loop.evaluation.calibration_v037 import (
    calibration_adjusted_evidence_gate,
    fit_development_isotonic_map,
)
from epistemic_loop.evaluation.v037 import _calibration


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth-root", type=Path, default=Path(".controller_truth/v038"))
    parser.add_argument("--key-file", type=Path, default=Path(".state/v038/controller.key"))
    parser.add_argument("--submission-root", type=Path, default=Path(".runs/v038/agent_outputs"))
    parser.add_argument("--suite-root", type=Path, default=Path(".runs/v038"))
    parser.add_argument("--output", type=Path, default=Path(".runs/v038/calibration_c1.json"))
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit("v0.3.8 development calibration is already locked")
    lock = json.loads((arguments.suite_root / "development_agent_runs.lock.json").read_text())
    if not lock.get("all_outputs_locked_before_hidden_evaluation"):
        raise SystemExit("development outputs must be locked before development truth is opened")
    key = arguments.key_file.read_bytes().strip()
    probabilities: list[float] = []
    outcomes: list[bool] = []
    per_agent: dict[str, tuple[list[float], list[bool]]] = {}
    for suite_id in V038_DEV_SUITE_IDS:
        truth = decrypt_v037_suite(arguments.truth_root / f"{suite_id}.manifest.enc", key)
        alias_lookup = {(alias.run_id, alias.opaque_pack_id): alias.canonical_pack_id for alias in truth.aliases}
        present = {context.canonical_pack_id: context.structure_present for context in truth.context_truth}
        for run_id in V038_DEV_EXECUTED_RUN_IDS[suite_id]:
            loaded = load_v038_submission(arguments.submission_root / suite_id / run_id / "agent_submission.json")
            agent_bucket = per_agent.setdefault(loaded.core.agent_id, ([], []))
            for pack in loaded.core.packs:
                canonical = alias_lookup[(run_id, pack.opaque_pack_id)]
                probabilities.append(pack.confidence.p_structure_exists)
                outcomes.append(present[canonical])
                agent_bucket[0].append(pack.confidence.p_structure_exists)
                agent_bucket[1].append(present[canonical])
    calibration_map = fit_development_isotonic_map(tuple(probabilities), tuple(outcomes))
    agent_records = {}
    for agent_id, (agent_probabilities, agent_outcomes) in sorted(per_agent.items()):
        summary = _calibration(agent_probabilities, agent_outcomes)
        agent_records[agent_id] = {
            "development_samples": len(agent_probabilities),
            "development_brier": summary.brier,
            "development_ece": summary.ece,
            "c2_evidence_gate": asdict(calibration_adjusted_evidence_gate(summary.ece)),
        }
    payload = {
        "version": "0.3.8",
        "fit_on": "development suites only",
        "development_suites": list(V038_DEV_SUITE_IDS),
        "training_samples": calibration_map.training_samples,
        "isotonic_map": {
            "upper_bounds": list(calibration_map.upper_bounds),
            "calibrated_values": list(calibration_map.calibrated_values),
        },
        "per_agent": agent_records,
    }
    arguments.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"locked": True, "training_samples": calibration_map.training_samples}, indent=2))


if __name__ == "__main__":
    main()
