#!/usr/bin/env python3
"""Build and lock the single Track B (IEEE-CIS blind bridge) real-data suite.

One suite, 12 run_id slots (3 execution configurations x 4 replicates), all opaque-salted
independently. See docs/v041_track_b_preregistration.json for the full design, frozen
before this script was first run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from epistemic_loop.benchmark.v038_repro_suite import V038_NULL_PROVENANCE_FIELDS
from epistemic_loop.benchmark.v041_track_b_suite import (
    V041_TRACKB_CONFIGS,
    V041_TRACKB_MASTER_SEED,
    V041_TRACKB_MAX_CYCLES_PER_PACK,
    V041_TRACKB_RUN_IDS,
    V041_TRACKB_SUITE_ID,
    build_v041_track_b_suite,
)
from epistemic_loop.controller.v040_agent import v040_submission_contract


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path(".data/ieee-cis"))
    parser.add_argument("--output-root", type=Path, default=Path(".runs/v041"))
    parser.add_argument("--truth-root", type=Path, default=Path(".controller_truth/v041"))
    parser.add_argument("--key-file", type=Path, default=Path(".state/v040/controller.key"))
    parser.add_argument("--lock-file", type=Path, default=Path(".runs/v041/trackb_suite_lock.json"))
    arguments = parser.parse_args()
    if arguments.lock_file.exists():
        raise SystemExit(f"Track B suite already locked at {arguments.lock_file}; delete deliberately to rebuild")
    if not arguments.key_file.exists():
        raise SystemExit(f"expected an existing controller key at {arguments.key_file}")
    key = arguments.key_file.read_bytes().strip()
    prompt_paths = {
        "p1": Path("prompts/generic_research_agent/v040_p1.md"),
        "p3": Path("prompts/generic_research_agent/v040_p3.md"),
    }
    policy_contract = {
        "null_policy": {
            "full_refit": True,
            "check_every": 5,
            "minimum": 5,
            "maximum": 30,
            "stops": ["futility", "early_support", "max_replicates"],
            "provenance_required": True,
            "provenance_fields": list(V038_NULL_PROVENANCE_FIELDS),
        },
        "confidence_fields": [
            "p_structure_exists",
            "p_evidence_sufficient",
            "p_actionable",
            "p_positive_transfer",
        ],
        "hidden_regions": ["structure_confirmation", "transfer_sealed"],
        "translations_required": 2,
        "fresh_context_per_run": True,
        "lineage_continuity_enforced": True,
        "terminal_resolution_consistency_enforced": True,
        "implication_provenance_required": True,
    }
    output_root = arguments.output_root / V041_TRACKB_SUITE_ID
    result = build_v041_track_b_suite(
        data_root=arguments.data_root,
        output_root=output_root,
        truth_root=arguments.truth_root,
        key=key,
        prompt_paths=prompt_paths,
        policy_contract=policy_contract,
        suite_id=V041_TRACKB_SUITE_ID,
        master_seed=V041_TRACKB_MASTER_SEED,
        configs=V041_TRACKB_CONFIGS,
        run_ids=V041_TRACKB_RUN_IDS,
        max_cycles_per_pack=V041_TRACKB_MAX_CYCLES_PER_PACK,
    )
    contract = v040_submission_contract()
    for run_root in result.run_roots.values():
        path = Path(run_root) / "submission_contract.json"
        path.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    payload = {
        "version": "0.4.1",
        "study": "track-b-ieee-cis-blind-bridge",
        "suite_id": V041_TRACKB_SUITE_ID,
        "max_cycles_per_pack": V041_TRACKB_MAX_CYCLES_PER_PACK,
        "execution_configurations": {run: dict(config) for run, config in V041_TRACKB_CONFIGS.items()},
        "total_runs": len(V041_TRACKB_RUN_IDS),
        "fresh_llm_context_per_run": True,
        "prompts_frozen_before_generation": True,
        "prompt_hashes": {
            name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in sorted(prompt_paths.items())
        },
        "policy_contract_sha256": hashlib.sha256(json.dumps(policy_contract, sort_keys=True).encode()).hexdigest(),
        "result": asdict(result),
    }
    arguments.lock_file.parent.mkdir(parents=True, exist_ok=True)
    arguments.lock_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "locked": True,
                "suite_id": V041_TRACKB_SUITE_ID,
                "runs": len(V041_TRACKB_RUN_IDS),
                "preflight_passed": result.preflight_passed,
                "preflight": [
                    {
                        "pack": item.canonical_pack_id,
                        "structure_present": item.structure_present,
                        "identifiable": item.identifiable,
                        "research_gain": round(item.research_oracle_gain, 4),
                        "confirmation_gain": round(item.confirmation_oracle_gain, 4),
                        "transfer_gain": round(item.transfer_oracle_gain, 4),
                    }
                    for item in result.preflight
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
