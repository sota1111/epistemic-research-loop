#!/usr/bin/env python3
"""Build and lock the four v0.3.9 qualification suites before agent execution."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from cryptography.fernet import Fernet

from epistemic_loop.benchmark.v039_repro_suite import (
    V039_NULL_PROVENANCE_FIELDS,
    V039_QUAL_SUITE_IDS,
    build_v039_suite,
)
from epistemic_loop.controller.v039_agent import v039_submission_contract


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=Path(".runs/v039"))
    parser.add_argument("--truth-root", type=Path, default=Path(".controller_truth/v039"))
    parser.add_argument("--key-file", type=Path, default=Path(".state/v039/controller.key"))
    parser.add_argument("--rows-per-context", type=int, default=900)
    arguments = parser.parse_args()
    lock_path = arguments.output_root / "suite_set_lock.json"
    if lock_path.exists():
        raise SystemExit("v0.3.9 suite set is already locked and immutable")
    arguments.key_file.parent.mkdir(parents=True, exist_ok=True)
    if arguments.key_file.exists():
        key = arguments.key_file.read_bytes().strip()
    else:
        key = Fernet.generate_key()
        arguments.key_file.write_bytes(key + b"\n")
        arguments.key_file.chmod(0o600)
    prompt_path = Path("prompts/generic_research_agent/v038_p1.md")
    policy_contract = {
        "null_policy": {
            "full_refit": True,
            "check_every": 5,
            "minimum": 5,
            "maximum": 30,
            "stops": ["futility", "early_support", "max_replicates"],
            "provenance_required": True,
            "provenance_fields": list(V039_NULL_PROVENANCE_FIELDS),
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
    }
    contract = v039_submission_contract()
    results: list[dict[str, object]] = []
    for suite_id in V039_QUAL_SUITE_IDS:
        result = build_v039_suite(
            suite_id=suite_id,
            output_root=arguments.output_root / suite_id,
            truth_root=arguments.truth_root,
            key=key,
            prompt_path=prompt_path,
            policy_contract=policy_contract,
            rows_per_context=arguments.rows_per_context,
        )
        for run_root in result.run_roots.values():
            path = Path(run_root) / "submission_contract.json"
            path.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
        results.append(asdict(result))
    payload = {
        "version": "0.3.9",
        "qualification_suite_ids": list(V039_QUAL_SUITE_IDS),
        "agent_runs_per_qualification_suite": 6,
        "total_qualification_agent_runs": 24,
        "fresh_llm_context_per_run": True,
        "calibration_c1_source": ".runs/v038/calibration_c1.json (locked v0.3.8 development fit, reused)",
        "prompts_frozen_before_generation": True,
        "prompt_hashes": {"p1": hashlib.sha256(prompt_path.read_bytes()).hexdigest()},
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
