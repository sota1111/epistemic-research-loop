#!/usr/bin/env python3
"""Build and lock one v0.4.2 multi-competition suite for a preregistered CompetitionSpec.

Generic across competitions (see epistemic_loop.benchmark.v042_competitions); the design
itself (schema, matched-negative construction, identifiability preflight with retry,
12-run execution-configuration diversity) is otherwise unchanged from Track B.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from epistemic_loop.benchmark.v038_repro_suite import V038_NULL_PROVENANCE_FIELDS
from epistemic_loop.benchmark.v042_competitions import COMPETITION_REGISTRY
from epistemic_loop.benchmark.v042_multi_competition_suite import (
    V042_EXECUTION_CONFIGS,
    V042_MASTER_SEED,
    V042_MAX_CYCLES_PER_PACK,
    V042_RUN_IDS,
    V043_SOL_EFFORT_CONFIGS,
    V043_SOL_EFFORT_R2_IEEE_CIS_CONFIGS,
    V043_SOL_EFFORT_R2_IEEE_CIS_RUN_IDS,
    V043_SOL_EFFORT_R2_SANTANDER_CONFIGS,
    V043_SOL_EFFORT_R2_SANTANDER_RUN_IDS,
    V043_SOL_EFFORT_R3_IEEE_CIS_CONFIGS,
    V043_SOL_EFFORT_R3_IEEE_CIS_RUN_IDS,
    V043_SOL_EFFORT_R3_SANTANDER_CONFIGS,
    V043_SOL_EFFORT_R3_SANTANDER_RUN_IDS,
    V043_SOL_EFFORT_R4_IEEE_CIS_CONFIGS,
    V043_SOL_EFFORT_R4_IEEE_CIS_RUN_IDS,
    V043_SOL_EFFORT_R4_SANTANDER_CONFIGS,
    V043_SOL_EFFORT_R4_SANTANDER_RUN_IDS,
    V043_SOL_EFFORT_RUN_IDS,
    build_v042_suite,
)
from epistemic_loop.controller.v040_agent import v040_submission_contract

#: --config-set selects which preregistered execution-configuration mapping this suite
#: uses; "default" is the original 3-config (opus-P1/opus-P3/sol-P3) design, "sol-effort"
#: is the v0.4.3 sol-only reasoning-effort diversity screening round, "sol-effort-r2-*" are
#: the per-competition confirmatory follow-ups (see V043_SOL_EFFORT_CONFIGS's docstring in
#: v042_multi_competition_suite.py).
_CONFIG_SETS: dict[str, tuple[object, tuple[str, ...]]] = {
    "default": (V042_EXECUTION_CONFIGS, V042_RUN_IDS),
    "sol-effort": (V043_SOL_EFFORT_CONFIGS, V043_SOL_EFFORT_RUN_IDS),
    "sol-effort-r2-a": (V043_SOL_EFFORT_R2_IEEE_CIS_CONFIGS, V043_SOL_EFFORT_R2_IEEE_CIS_RUN_IDS),
    "sol-effort-r2-b": (V043_SOL_EFFORT_R2_SANTANDER_CONFIGS, V043_SOL_EFFORT_R2_SANTANDER_RUN_IDS),
    "sol-effort-r3-a": (V043_SOL_EFFORT_R3_IEEE_CIS_CONFIGS, V043_SOL_EFFORT_R3_IEEE_CIS_RUN_IDS),
    "sol-effort-r3-b": (V043_SOL_EFFORT_R3_SANTANDER_CONFIGS, V043_SOL_EFFORT_R3_SANTANDER_RUN_IDS),
    "sol-effort-r4-a": (V043_SOL_EFFORT_R4_IEEE_CIS_CONFIGS, V043_SOL_EFFORT_R4_IEEE_CIS_RUN_IDS),
    "sol-effort-r4-b": (V043_SOL_EFFORT_R4_SANTANDER_CONFIGS, V043_SOL_EFFORT_R4_SANTANDER_RUN_IDS),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--competition-id", required=True, choices=sorted(COMPETITION_REGISTRY))
    parser.add_argument("--suite-id", required=True)
    parser.add_argument("--config-set", default="default", choices=sorted(_CONFIG_SETS))
    parser.add_argument("--output-root", type=Path, default=Path(".runs/v042"))
    parser.add_argument("--truth-root", type=Path, default=Path(".controller_truth/v042"))
    parser.add_argument("--key-file", type=Path, default=Path(".state/v040/controller.key"))
    parser.add_argument("--lock-file", type=Path, default=None)
    arguments = parser.parse_args()
    execution_configs, run_ids = _CONFIG_SETS[arguments.config_set]
    if arguments.lock_file is None:
        arguments.lock_file = arguments.output_root / f"{arguments.suite_id}_suite_lock.json"
    if arguments.lock_file.exists():
        raise SystemExit(f"suite already locked at {arguments.lock_file}; delete deliberately to rebuild")
    if not arguments.key_file.exists():
        raise SystemExit(f"expected an existing controller key at {arguments.key_file}")
    spec = COMPETITION_REGISTRY[arguments.competition_id]
    if not spec.data_path.exists():
        raise SystemExit(f"competition data not found at {spec.data_path}; fetch it before building")
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
    output_root = arguments.output_root / arguments.suite_id
    result = build_v042_suite(
        spec,
        output_root=output_root,
        truth_root=arguments.truth_root,
        key=key,
        prompt_paths=prompt_paths,
        policy_contract=policy_contract,
        suite_id=arguments.suite_id,
        master_seed=V042_MASTER_SEED,
        configs=execution_configs,
        run_ids=run_ids,
        max_cycles_per_pack=V042_MAX_CYCLES_PER_PACK,
    )
    contract = v040_submission_contract()
    for run_root in result.run_roots.values():
        path = Path(run_root) / "submission_contract.json"
        path.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    payload = {
        "version": "0.4.2",
        "study": "v042-multi-competition-blind-bridge",
        "competition_id": arguments.competition_id,
        "suite_id": arguments.suite_id,
        "split_strategy": spec.split_strategy,
        "max_cycles_per_pack": V042_MAX_CYCLES_PER_PACK,
        "execution_configurations": {run: dict(config) for run, config in execution_configs.items()},
        "total_runs": len(run_ids),
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
                "competition_id": arguments.competition_id,
                "suite_id": arguments.suite_id,
                "split_strategy": spec.split_strategy,
                "runs": len(run_ids),
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
