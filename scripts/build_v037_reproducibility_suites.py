#!/usr/bin/env python3
"""Build and lock all four v0.3.7 qualification suites before agent execution."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from cryptography.fernet import Fernet

from epistemic_loop.benchmark.v037_repro_suite import V037_SUITE_IDS, build_v037_suite
from epistemic_loop.controller.v037_agent import v037_submission_contract


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=Path(".runs/v037"))
    parser.add_argument("--truth-root", type=Path, default=Path(".controller_truth/v037"))
    parser.add_argument("--key-file", type=Path, default=Path(".state/v037/controller.key"))
    parser.add_argument("--rows-per-context", type=int, default=900)
    arguments = parser.parse_args()
    lock_path = arguments.output_root / "primary_suite_set_lock.json"
    if lock_path.exists():
        raise SystemExit("v0.3.7 suite set is already locked and immutable")
    arguments.key_file.parent.mkdir(parents=True, exist_ok=True)
    if arguments.key_file.exists():
        key = arguments.key_file.read_bytes().strip()
    else:
        key = Fernet.generate_key()
        arguments.key_file.write_bytes(key + b"\n")
        arguments.key_file.chmod(0o600)
    prompts = {
        "p0": Path("prompts/generic_research_agent/v037_p0.md"),
        "p1": Path("prompts/generic_research_agent/v037_p1.md"),
    }
    policy_contract = {
        "null_policy": {
            "full_refit": True,
            "check_every": 5,
            "minimum": 5,
            "maximum": 30,
            "stops": ["futility", "early_support", "max_replicates"],
        },
        "confidence_fields": [
            "p_structure_exists",
            "p_evidence_sufficient",
            "p_actionable",
            "p_positive_transfer",
        ],
        "hidden_regions": ["structure_confirmation", "transfer_sealed"],
        "translations_required": 2,
    }
    contract = v037_submission_contract()
    results: list[dict[str, object]] = []
    for index, suite_id in enumerate(V037_SUITE_IDS, start=1):
        result = build_v037_suite(
            suite_id=suite_id,
            suite_index=index,
            output_root=arguments.output_root / suite_id,
            truth_root=arguments.truth_root,
            key=key,
            prompt_paths=prompts,
            policy_contract=policy_contract,
            rows_per_context=arguments.rows_per_context,
        )
        for run_root in result.run_roots.values():
            path = Path(run_root) / "submission_contract.json"
            path.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
        results.append(asdict(result))
    prompt_hashes = {name: _sha256(path) for name, path in prompts.items()}
    payload = {
        "version": "0.3.7",
        "suite_ids": list(V037_SUITE_IDS),
        "suite_count": len(V037_SUITE_IDS),
        "agent_runs_per_suite": 6,
        "total_agent_runs": 24,
        "prompts_frozen_before_generation": True,
        "prompt_hashes": prompt_hashes,
        "policy_contract_sha256": hashlib.sha256(json.dumps(policy_contract, sort_keys=True).encode()).hexdigest(),
        "results": results,
    }
    arguments.output_root.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    main()
