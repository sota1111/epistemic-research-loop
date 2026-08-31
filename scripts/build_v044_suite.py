#!/usr/bin/env python3
"""Build one v0.4.4 full-feature suite (V044_SOL_EFFORT_CONFIGS, 8 runs by default).

See docs/verification/v044_full_feature_pilot_preregistration.md and
docs/c_lite_v044_policy.md.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from dataclasses import dataclass as _dataclass
from pathlib import Path

from cryptography.fernet import Fernet

from epistemic_loop.benchmark.v042_competitions import COMPETITION_REGISTRY
from epistemic_loop.benchmark.v044_full_feature_pilot import (
    V044_MASTER_SEED,
    V044_R2_CONFIGS,
    V044_R2_RUN_IDS,
    V044_R3_CONFIGS,
    V044_R3_RUN_IDS,
    V044_R4_CONFIGS,
    V044_R4_RUN_IDS,
    V044_R5_CONFIGS,
    V044_R5_RUN_IDS,
    V044_SOL_EFFORT_CONFIGS,
    V044_SOL_EFFORT_RUN_IDS,
    V046_LOW_FB_CONFIGS,
    V046_LOW_FB_RUN_IDS,
    V046_LOW_NOFB_CONFIGS,
    V046_LOW_NOFB_RUN_IDS,
    build_v044_suite,
)


@_dataclass(frozen=True)
class _ConfigSet:
    configs: object
    run_ids: tuple[str, ...]
    column_limit: int | None = None
    enable_confirmation_scoring: bool = True


#: "screening"/"confirm"/"scale" = v0.4.4-b's three rounds (full columns, feedback loop
#: enabled, docs/c_lite_v044_policy.md). "10col-fb"/"full-nofb" = v0.4.5's factorial cells
#: C/D and E/F (docs/c_lite_v045_policy.md SS2-3) -- reintroduce the 10-column limit with
#: feedback still on, and drop feedback with columns still full, to separate the two
#: factors that v0.4.4-b changed together.
_CONFIG_SETS: dict[str, _ConfigSet] = {
    "screening": _ConfigSet(V044_SOL_EFFORT_CONFIGS, V044_SOL_EFFORT_RUN_IDS),
    "confirm": _ConfigSet(V044_R2_CONFIGS, V044_R2_RUN_IDS),
    "scale": _ConfigSet(V044_R3_CONFIGS, V044_R3_RUN_IDS),
    "10col-fb": _ConfigSet(V044_R4_CONFIGS, V044_R4_RUN_IDS, column_limit=10, enable_confirmation_scoring=True),
    "full-nofb": _ConfigSet(V044_R5_CONFIGS, V044_R5_RUN_IDS, column_limit=None, enable_confirmation_scoring=False),
    "low-nofb": _ConfigSet(
        V046_LOW_NOFB_CONFIGS, V046_LOW_NOFB_RUN_IDS, column_limit=None, enable_confirmation_scoring=False
    ),
    "low-fb": _ConfigSet(V046_LOW_FB_CONFIGS, V046_LOW_FB_RUN_IDS, column_limit=None, enable_confirmation_scoring=True),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--competition-id", required=True, choices=sorted(COMPETITION_REGISTRY))
    parser.add_argument("--suite-id", required=True)
    parser.add_argument("--config-set", default="screening", choices=sorted(_CONFIG_SETS))
    parser.add_argument("--output-root", type=Path, default=Path(".runs/v044"))
    parser.add_argument("--truth-root", type=Path, default=Path(".controller_truth/v044"))
    parser.add_argument("--key-file", type=Path, default=Path(".state/v040/controller.key"))
    parser.add_argument("--scorer-key-file", type=Path, default=Path(".state/v044/scorer.key"))
    parser.add_argument("--prompt-p1", type=Path, default=None)
    parser.add_argument("--prompt-p3", type=Path, default=None)
    parser.add_argument("--lock-file", type=Path, default=None)
    arguments = parser.parse_args()
    config_set = _CONFIG_SETS[arguments.config_set]
    prompt_dir = Path("prompts/generic_research_agent")
    suffix = "" if config_set.enable_confirmation_scoring else "_noscore"
    if arguments.prompt_p1 is None:
        arguments.prompt_p1 = prompt_dir / f"v044_p1{suffix}.md"
    if arguments.prompt_p3 is None:
        arguments.prompt_p3 = prompt_dir / f"v044_p3{suffix}.md"
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
        configs=config_set.configs,
        run_ids=config_set.run_ids,
        master_seed=V044_MASTER_SEED,
        column_limit=config_set.column_limit,
        enable_confirmation_scoring=config_set.enable_confirmation_scoring,
    )
    payload = {
        "version": "0.4.4",
        "study": "v044-full-feature-suite",
        "competition_id": arguments.competition_id,
        "suite_id": arguments.suite_id,
        "config_set": arguments.config_set,
        "column_limit": config_set.column_limit,
        "enable_confirmation_scoring": config_set.enable_confirmation_scoring,
        "execution_configurations": {run: dict(config) for run, config in config_set.configs.items()},
        "total_runs": len(config_set.run_ids),
        "result": asdict(result),
    }
    arguments.lock_file.parent.mkdir(parents=True, exist_ok=True)
    arguments.lock_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
