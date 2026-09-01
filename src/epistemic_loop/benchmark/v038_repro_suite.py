"""Blind v0.3.8 suites: fresh-context reproducibility with machine-audited provenance.

v0.3.8 keeps the v0.3.7 generator families, pack ladder, and opaque-view machinery
unchanged so that the intervention set (fresh LLM context per run, mandatory null
provenance artifacts, P1 as the single frozen prompt, controller-enforced lineage
continuity) is the only difference against the v0.3.7 baseline. Suite identities,
master seeds, and prompt hashes are new; the opened v0.3.7 suites are never reused.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

from epistemic_loop.benchmark.v037_repro_suite import (
    CANONICAL_FEATURES as V037_CANONICAL_FEATURES,
)
from epistemic_loop.benchmark.v037_repro_suite import (
    PACK_DEFINITIONS,
    V037_AGENT_IDS,
    V037_RUN_IDS,
    V037_SAMPLING_SEEDS,
    V037AliasTruth,
    V037SuiteBuildResult,
    V037SuiteTruth,
    _agent_rows,
    _derive_int,
    _generate_context,
    _independent_identifiability,
    _opaque_id,
    _parse_run_id,
    _sha256_file,
    _visible_column_map,
    _write_json,
    preflight_v037_suite,
)
from epistemic_loop.benchmark.v037_repro_suite import (
    V037ContextTruth as V038ContextTruth,
)

V038_QUAL_SUITE_IDS = tuple(f"v038-qual-c{index:02d}" for index in range(1, 5))
V038_DEV_SUITE_IDS = ("v038-dev-d01", "v038-dev-d02")
V038_AGENT_IDS = V037_AGENT_IDS
V038_SAMPLING_SEEDS = V037_SAMPLING_SEEDS
V038_RUN_IDS = V037_RUN_IDS
V038_QUAL_MASTER_SEED = 20260901
V038_DEV_MASTER_SEED = 20260902

#: Development runs are a preregistered subset: two fresh runs per agent identity across
#: the two development suites, with both sampling seeds represented for every agent.
V038_DEV_EXECUTED_RUN_IDS: Mapping[str, tuple[str, ...]] = {
    "v038-dev-d01": ("agent-01-s17", "agent-02-s42", "agent-03-s17"),
    "v038-dev-d02": ("agent-01-s42", "agent-02-s17", "agent-03-s42"),
}

V038_LINEAGE_POLICIES = ("deterministic_best", "posterior_commit", "two_hit_maturation")

V038_NULL_PROVENANCE_FIELDS = (
    "replicate_index",
    "permutation_hash",
    "preserved_statistics",
    "feature_manifest_hash",
    "fold_plan_hash",
    "model_fit_manifest_hash",
    "oof_prediction_hash",
    "gain",
)


def v038_suite_index(suite_id: str) -> int:
    """Return the 1-based design index of a preregistered v0.3.8 suite."""

    for group in (V038_QUAL_SUITE_IDS, V038_DEV_SUITE_IDS):
        if suite_id in group:
            return group.index(suite_id) + 1
    raise ValueError(f"unknown v0.3.8 suite identity: {suite_id}")


def v038_lineage_assignment(suite_index: int, run_index: int) -> str:
    """Balanced rotation of the three lineage policies; the prompt arm is always P1."""

    return V038_LINEAGE_POLICIES[(run_index + suite_index - 1) % len(V038_LINEAGE_POLICIES)]


def build_v038_suite(
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
    """Create one immutable v0.3.8 suite with six independently permuted run views."""

    if suite_id in V038_QUAL_SUITE_IDS:
        master_seed = V038_QUAL_MASTER_SEED
    elif suite_id in V038_DEV_SUITE_IDS:
        master_seed = V038_DEV_MASTER_SEED
    else:
        raise ValueError("v0.3.8 requires a preregistered qualification or development suite identity")
    return build_versioned_suite(
        version="0.3.8",
        suite_id=suite_id,
        suite_index=v038_suite_index(suite_id),
        master_seed=master_seed,
        output_root=output_root,
        truth_root=truth_root,
        key=key,
        prompt_path=prompt_path,
        policy_contract=policy_contract,
        contexts_per_pack=contexts_per_pack,
        rows_per_context=rows_per_context,
    )


def build_versioned_suite(
    *,
    version: str,
    suite_id: str,
    suite_index: int,
    master_seed: int,
    output_root: Path,
    truth_root: Path,
    key: bytes,
    prompt_path: Path,
    policy_contract: Mapping[str, Any],
    contexts_per_pack: int = 3,
    rows_per_context: int = 900,
) -> V037SuiteBuildResult:
    """Shared v0.3.8-family suite builder; later revisions supply new identities and seeds."""

    if contexts_per_pack < 3 or rows_per_context < 600:
        raise ValueError("aggregate promotion requires three contexts and at least 600 rows")
    if output_root.exists() or (truth_root / f"{suite_id}.manifest.enc").exists():
        raise FileExistsError(f"v{version} suites are immutable; use a new suite identity")
    Fernet(key)
    prompt_hashes = {"p1": _sha256_file(prompt_path)}
    policy_hash = hashlib.sha256(json.dumps(policy_contract, sort_keys=True).encode()).hexdigest()
    if not policy_contract.get("null_policy", {}).get("provenance_required"):
        raise ValueError(f"v{version} requires per-replicate null provenance in the locked policy contract")

    canonical: dict[str, list[tuple[str, list[dict[str, Any]], V038ContextTruth]]] = {}
    for pack_index, definition in enumerate(PACK_DEFINITIONS, start=1):
        pack_id = f"pack-{pack_index:02d}"
        contexts: list[tuple[str, list[dict[str, Any]], V038ContextTruth]] = []
        for context_index in range(1, contexts_per_pack + 1):
            context_id = f"context-{context_index:02d}"
            seed = _derive_int(master_seed, suite_id, pack_id, context_id)
            rows = _generate_context(definition, seed=seed, count=rows_per_context)
            research_end = int(len(rows) * 0.60)
            confirmation_end = int(len(rows) * 0.80)
            research = rows[:research_end]
            confirmation = rows[research_end:confirmation_end]
            transfer = rows[confirmation_end:]
            contexts.append(
                (
                    context_id,
                    rows,
                    V038ContextTruth(
                        canonical_pack_id=pack_id,
                        canonical_context_id=context_id,
                        family=definition.family,
                        structure_present=definition.structure_present,
                        predictive_utility=definition.predictive_utility,
                        matched_pair=definition.matched_pair,
                        ladder_level=definition.ladder_level,
                        generator_seed=seed,
                        research_targets=tuple(int(row["target"]) for row in research),
                        confirmation_targets=tuple(int(row["target"]) for row in confirmation),
                        transfer_targets=tuple(int(row["target"]) for row in transfer),
                        oracle_research_predictions=tuple(float(row["_oracle"]) for row in research),
                        control_research_predictions=tuple(float(row["_control"]) for row in research),
                        oracle_confirmation_predictions=tuple(float(row["_oracle"]) for row in confirmation),
                        control_confirmation_predictions=tuple(float(row["_control"]) for row in confirmation),
                        oracle_transfer_predictions=tuple(float(row["_oracle"]) for row in transfer),
                        control_transfer_predictions=tuple(float(row["_control"]) for row in transfer),
                        independent_identifiability=_independent_identifiability(definition),
                    ),
                )
            )
        canonical[pack_id] = contexts

    output_root.mkdir(parents=True)
    truth_root.mkdir(parents=True, exist_ok=True)
    aliases: list[V037AliasTruth] = []
    public_hashes: list[str] = []
    for run_index, run_id in enumerate(V038_RUN_IDS):
        agent_id, sampling_seed = _parse_run_id(run_id)
        policy = v038_lineage_assignment(suite_index, run_index)
        run_root = output_root / "agent_views" / run_id
        run_root.mkdir(parents=True)
        (run_root / "agent_prompt.md").write_bytes(prompt_path.read_bytes())
        pack_order = list(canonical)
        random.Random(_derive_int(master_seed, suite_id, run_id, "pack-order")).shuffle(pack_order)
        packet_packs: list[dict[str, Any]] = []
        for canonical_pack_id in pack_order:
            opaque_pack_id = _opaque_id(key, suite_id, run_id, canonical_pack_id, "pack")
            pack_root = run_root / opaque_pack_id
            pack_root.mkdir()
            column_map = _visible_column_map(key, suite_id, run_id, canonical_pack_id)
            context_order = list(canonical[canonical_pack_id])
            random.Random(_derive_int(master_seed, suite_id, run_id, canonical_pack_id)).shuffle(context_order)
            context_entries: list[dict[str, Any]] = []
            for canonical_context_id, rows, _truth in context_order:
                research_end = int(len(rows) * 0.60)
                confirmation_end = int(len(rows) * 0.80)
                research = _agent_rows(
                    rows[:research_end],
                    column_map,
                    include_target=True,
                    seed=_derive_int(master_seed, run_id, canonical_context_id, "research"),
                )
                confirmation = _agent_rows(
                    rows[research_end:confirmation_end],
                    column_map,
                    include_target=False,
                    seed=_derive_int(master_seed, run_id, canonical_context_id, "confirmation"),
                )
                transfer = _agent_rows(
                    rows[confirmation_end:],
                    column_map,
                    include_target=False,
                    seed=_derive_int(master_seed, run_id, canonical_context_id, "transfer"),
                )
                opaque_context_id = _opaque_id(
                    key, suite_id, run_id, canonical_pack_id, canonical_context_id, "context"
                )
                research_name = f"{opaque_context_id}.research.json"
                confirmation_name = f"{opaque_context_id}.confirmation.json"
                transfer_name = f"{opaque_context_id}.transfer.json"
                _write_json(pack_root / research_name, research)
                _write_json(pack_root / confirmation_name, confirmation)
                _write_json(pack_root / transfer_name, transfer)
                target_by_row = {int(row["row_id"]): int(row["target"]) for row in rows}
                aliases.append(
                    V037AliasTruth(
                        run_id=run_id,
                        agent_id=agent_id,
                        sampling_seed=sampling_seed,
                        opaque_pack_id=opaque_pack_id,
                        opaque_context_id=opaque_context_id,
                        canonical_pack_id=canonical_pack_id,
                        canonical_context_id=canonical_context_id,
                        canonical_to_visible_columns=column_map,
                        confirmation_targets_in_view_order=tuple(
                            target_by_row[int(row["row_id"])] for row in confirmation
                        ),
                        transfer_targets_in_view_order=tuple(target_by_row[int(row["row_id"])] for row in transfer),
                    )
                )
                context_entries.append(
                    {
                        "opaque_context_id": opaque_context_id,
                        "research_file": str((Path(opaque_pack_id) / research_name).as_posix()),
                        "confirmation_file": str((Path(opaque_pack_id) / confirmation_name).as_posix()),
                        "transfer_file": str((Path(opaque_pack_id) / transfer_name).as_posix()),
                        "research_rows": len(research),
                        "confirmation_rows": len(confirmation),
                        "transfer_rows": len(transfer),
                    }
                )
            packet_packs.append(
                {
                    "opaque_pack_id": opaque_pack_id,
                    "feature_columns": sorted(column_map.values()),
                    "target_column": "target",
                    "contexts": context_entries,
                }
            )
        packet = {
            "version": version,
            "suite_id": suite_id,
            "run_id": run_id,
            "agent_id": agent_id,
            "sampling_seed": sampling_seed,
            "prompt_arm": "p1",
            "lineage_policy": policy,
            "prompt_hash": prompt_hashes["p1"],
            "policy_contract_hash": policy_hash,
            "cross_run_information": "none",
            "fresh_context_required": True,
            "max_cycles_per_pack": 4,
            "null_policy": policy_contract["null_policy"],
            "confidence_fields": policy_contract["confidence_fields"],
            "null_provenance_fields": list(V038_NULL_PROVENANCE_FIELDS),
            "packs": packet_packs,
        }
        _write_json(run_root / "agent_packet.json", packet)
        public_hashes.append(_sha256_file(run_root / "agent_packet.json"))

    suite_truth = V037SuiteTruth(
        suite_id=suite_id,
        suite_index=suite_index,
        prompt_hashes=prompt_hashes,
        policy_contract_hash=policy_hash,
        generated_before_agent_runs=True,
        contexts_per_pack=contexts_per_pack,
        context_truth=tuple(item[2] for contexts in canonical.values() for item in contexts),
        aliases=tuple(aliases),
    )
    encrypted_path = truth_root / f"{suite_id}.manifest.enc"
    encrypted_path.write_bytes(Fernet(key).encrypt(json.dumps(_as_payload(suite_truth), sort_keys=True).encode()))
    encrypted_path.chmod(0o600)
    preflight = preflight_v037_suite(suite_truth)
    return V037SuiteBuildResult(
        suite_id=suite_id,
        run_roots={run_id: str(output_root / "agent_views" / run_id) for run_id in V038_RUN_IDS},
        encrypted_truth_path=str(encrypted_path),
        encrypted_truth_sha256=_sha256_file(encrypted_path),
        public_manifest_sha256=hashlib.sha256("".join(sorted(public_hashes)).encode()).hexdigest(),
        prompt_hashes=prompt_hashes,
        preflight=preflight,
        preflight_passed=all(item.identifiable for item in preflight),
    )


def _as_payload(truth: V037SuiteTruth) -> dict[str, Any]:
    from dataclasses import asdict

    return asdict(truth)


CANONICAL_FEATURES = V037_CANONICAL_FEATURES
