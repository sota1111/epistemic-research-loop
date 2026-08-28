#!/usr/bin/env python3
"""Build and lock the four suites for the codex sol reasoning-effort ablation.

Independent side-probe (not part of Track A generation 2): CLI/model/prompt-arm held
fixed at generation 1's C5 configuration, reasoning_effort varied across four levels.
Four suite instances (replicates) because the shared v0.3.7-lineage evaluator requires
exactly four distinct locked qualification suites. See
docs/v040_sol_effort_ablation_preregistration.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from epistemic_loop.benchmark.v038_repro_suite import V038_NULL_PROVENANCE_FIELDS
from epistemic_loop.benchmark.v040_grammar_suite import (
    V040_SOL_ABLATION_CONFIGS,
    V040_SOL_ABLATION_MASTER_SEED,
    V040_SOL_ABLATION_RUN_IDS,
    V040_SOL_ABLATION_SUITE_IDS,
    build_v040_suite,
)
from epistemic_loop.controller.v040_agent import v040_submission_contract


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=Path(".runs/v040"))
    parser.add_argument("--truth-root", type=Path, default=Path(".controller_truth/v040"))
    parser.add_argument("--key-file", type=Path, default=Path(".state/v040/controller.key"))
    parser.add_argument("--rows-per-context", type=int, default=900)
    arguments = parser.parse_args()
    lock_path = arguments.output_root / "sol_ablation_suite_set_lock.json"
    if lock_path.exists():
        raise SystemExit("v0.4.0 sol-ablation suite set is already locked and immutable")
    if not arguments.key_file.exists():
        raise SystemExit(f"expected an existing v0.4.0 controller key at {arguments.key_file}")
    key = arguments.key_file.read_bytes().strip()
    prompt_paths = {
        "p1": Path("prompts/generic_research_agent/v040_p1.md"),
        "p2": Path("prompts/generic_research_agent/v040_p2.md"),
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
    contract = v040_submission_contract()
    results: list[dict[str, object]] = []
    for suite_id in V040_SOL_ABLATION_SUITE_IDS:
        result = build_v040_suite(
            suite_id=suite_id,
            output_root=arguments.output_root / suite_id,
            truth_root=arguments.truth_root,
            key=key,
            prompt_paths=prompt_paths,
            policy_contract=policy_contract,
            rows_per_context=arguments.rows_per_context,
            suite_ids=V040_SOL_ABLATION_SUITE_IDS,
            master_seed=V040_SOL_ABLATION_MASTER_SEED,
            configs=V040_SOL_ABLATION_CONFIGS,
            run_ids=V040_SOL_ABLATION_RUN_IDS,
        )
        for run_root in result.run_roots.values():
            path = Path(run_root) / "submission_contract.json"
            path.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
        results.append(asdict(result))
    payload = {
        "version": "0.4.0",
        "study": "sol-effort-ablation",
        "suite_ids": list(V040_SOL_ABLATION_SUITE_IDS),
        "execution_configurations": {run: dict(config) for run, config in V040_SOL_ABLATION_CONFIGS.items()},
        "runs_per_suite": len(V040_SOL_ABLATION_RUN_IDS),
        "total_runs": len(V040_SOL_ABLATION_SUITE_IDS) * len(V040_SOL_ABLATION_RUN_IDS),
        "replicates_per_configuration": len(V040_SOL_ABLATION_SUITE_IDS),
        "fresh_llm_context_per_run": True,
        "prompts_frozen_before_generation": True,
        "prompt_hashes": {
            name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in sorted(prompt_paths.items())
        },
        "policy_contract_sha256": hashlib.sha256(json.dumps(policy_contract, sort_keys=True).encode()).hexdigest(),
        "results": results,
    }
    arguments.output_root.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "locked": True,
                "suites": [item["suite_id"] for item in results],
                "preflight_passed": all(item["preflight_passed"] for item in results),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
