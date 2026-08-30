#!/usr/bin/env python3
"""Build one v0.4.4 full-feature suite (V044_SOL_EFFORT_CONFIGS, 8 runs by default).

See docs/verification/v044_full_feature_pilot_preregistration.md and
docs/c_lite_v044_policy.md.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from cryptography.fernet import Fernet

from epistemic_loop.benchmark.v042_competitions import COMPETITION_REGISTRY
from epistemic_loop.benchmark.v044_full_feature_pilot import (
    V044_MASTER_SEED,
    V044_SOL_EFFORT_CONFIGS,
    V044_SOL_EFFORT_RUN_IDS,
    build_v044_suite,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--competition-id", required=True, choices=sorted(COMPETITION_REGISTRY))
    parser.add_argument("--suite-id", required=True)
    parser.add_argument("--output-root", type=Path, default=Path(".runs/v044"))
    parser.add_argument("--truth-root", type=Path, default=Path(".controller_truth/v044"))
    parser.add_argument("--key-file", type=Path, default=Path(".state/v040/controller.key"))
    parser.add_argument("--scorer-key-file", type=Path, default=Path(".state/v044/scorer.key"))
    parser.add_argument("--prompt-p1", type=Path, default=Path("prompts/generic_research_agent/v044_p1.md"))
    parser.add_argument("--prompt-p3", type=Path, default=Path("prompts/generic_research_agent/v044_p3.md"))
    parser.add_argument("--lock-file", type=Path, default=None)
    arguments = parser.parse_args()
    if arguments.lock_file is None:
        arguments.lock_file = arguments.output_root / f"{arguments.suite_id}_suite_lock.json"
    if arguments.lock_file.exists():
        raise SystemExit(f"suite already locked at {arguments.lock_file}; delete deliberately to rebuild")
    if not arguments.key_file.exists():
        raise SystemExit(f"expected an existing controller key at {arguments.key_file}")
    if not arguments.scorer_key_file.exists():
        arguments.scorer_key_file.parent.mkdir(parents=True, exist_ok=True)
        arguments.scorer_key_file.write_bytes(Fernet.generate_key())
        arguments.scorer_key_file.chmod(0o600)
    spec = COMPETITION_REGISTRY[arguments.competition_id]
    if not spec.data_path.exists():
        raise SystemExit(f"competition data not found at {spec.data_path}; fetch it before building")

    key = arguments.key_file.read_bytes().strip()
    scorer_key = arguments.scorer_key_file.read_bytes().strip()
    output_root = arguments.output_root / arguments.suite_id
    result = build_v044_suite(
        spec,
        output_root=output_root,
        truth_root=arguments.truth_root,
        key=key,
        scorer_key=scorer_key,
        prompt_paths={"p1": arguments.prompt_p1, "p3": arguments.prompt_p3},
        suite_id=arguments.suite_id,
        configs=V044_SOL_EFFORT_CONFIGS,
        run_ids=V044_SOL_EFFORT_RUN_IDS,
        master_seed=V044_MASTER_SEED,
    )
    payload = {
        "version": "0.4.4",
        "study": "v044-full-feature-suite",
        "competition_id": arguments.competition_id,
        "suite_id": arguments.suite_id,
        "execution_configurations": {run: dict(config) for run, config in V044_SOL_EFFORT_CONFIGS.items()},
        "total_runs": len(V044_SOL_EFFORT_RUN_IDS),
        "result": asdict(result),
    }
    arguments.lock_file.parent.mkdir(parents=True, exist_ok=True)
    arguments.lock_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
