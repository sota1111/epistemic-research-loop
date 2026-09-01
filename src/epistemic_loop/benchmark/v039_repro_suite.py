"""Blind v0.3.9 suites: v0.3.8 design plus contract-enforced terminal-resolution consistency.

v0.3.9 changes nothing about the generator families, pack ladder, opaque views, prompt,
or gates. The single intervention is agent-contract-side: a terminal resolution must be
internally consistent with the agent's own submitted evidence (see
``epistemic_loop.controller.v039_agent``). Suite identities and master seed are new; the
opened v0.3.8 suites are never reused. Calibration C1 is carried over from the locked
v0.3.8 development fit (preregistered; no new development runs).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from epistemic_loop.benchmark.v037_repro_suite import V037SuiteBuildResult
from epistemic_loop.benchmark.v038_repro_suite import (
    V038_AGENT_IDS,
    V038_LINEAGE_POLICIES,
    V038_NULL_PROVENANCE_FIELDS,
    V038_RUN_IDS,
    V038_SAMPLING_SEEDS,
    build_versioned_suite,
)

V039_QUAL_SUITE_IDS = tuple(f"v039-qual-e{index:02d}" for index in range(1, 5))
V039_AGENT_IDS = V038_AGENT_IDS
V039_SAMPLING_SEEDS = V038_SAMPLING_SEEDS
V039_RUN_IDS = V038_RUN_IDS
V039_QUAL_MASTER_SEED = 20260903
V039_LINEAGE_POLICIES = V038_LINEAGE_POLICIES
V039_NULL_PROVENANCE_FIELDS = V038_NULL_PROVENANCE_FIELDS


def build_v039_suite(
    *,
    suite_id: str,
    output_root: Path,
    truth_root: Path,
    key: bytes,
    prompt_path: Path,
    policy_contract: Mapping[str, Any],
    contexts_per_pack: int = 3,
    rows_per_context: int = 900,
) -> V037SuiteBuildResult:
    if suite_id not in V039_QUAL_SUITE_IDS:
        raise ValueError("v0.3.9 requires a preregistered qualification suite identity")
    return build_versioned_suite(
        version="0.3.9",
        suite_id=suite_id,
        suite_index=V039_QUAL_SUITE_IDS.index(suite_id) + 1,
        master_seed=V039_QUAL_MASTER_SEED,
        output_root=output_root,
        truth_root=truth_root,
        key=key,
        prompt_path=prompt_path,
        policy_contract=policy_contract,
        contexts_per_pack=contexts_per_pack,
        rows_per_context=rows_per_context,
    )
