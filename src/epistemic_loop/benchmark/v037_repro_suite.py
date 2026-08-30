"""Blind v0.3.7 suites for individual-agent reproducibility and blind-spot tests."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import Any

from cryptography.fernet import Fernet

V037_SUPERSEDED_SUITE_IDS = tuple(f"v037-repro-{index:02d}" for index in range(1, 5))
V037_SUITE_IDS = tuple(f"v037-repro-b{index:02d}" for index in range(1, 5))
V037_AGENT_IDS = ("agent-01", "agent-02", "agent-03")
V037_SAMPLING_SEEDS = (17, 42)
V037_RUN_IDS = tuple(f"{agent}-s{seed}" for agent in V037_AGENT_IDS for seed in V037_SAMPLING_SEEDS)


@dataclass(frozen=True)
class V037PackDefinition:
    family: str
    structure_present: bool
    predictive_utility: bool
    matched_pair: str
    ladder_level: int | None = None


@dataclass(frozen=True)
class V037ContextTruth:
    canonical_pack_id: str
    canonical_context_id: str
    family: str
    structure_present: bool
    predictive_utility: bool
    matched_pair: str
    ladder_level: int | None
    generator_seed: int
    research_targets: tuple[int, ...]
    confirmation_targets: tuple[int, ...]
    transfer_targets: tuple[int, ...]
    oracle_research_predictions: tuple[float, ...]
    control_research_predictions: tuple[float, ...]
    oracle_confirmation_predictions: tuple[float, ...]
    control_confirmation_predictions: tuple[float, ...]
    oracle_transfer_predictions: tuple[float, ...]
    control_transfer_predictions: tuple[float, ...]
    independent_identifiability: float


@dataclass(frozen=True)
class V037AliasTruth:
    run_id: str
    agent_id: str
    sampling_seed: int
    opaque_pack_id: str
    opaque_context_id: str
    canonical_pack_id: str
    canonical_context_id: str
    canonical_to_visible_columns: Mapping[str, str]
    confirmation_targets_in_view_order: tuple[int, ...]
    transfer_targets_in_view_order: tuple[int, ...]


@dataclass(frozen=True)
class V037SuiteTruth:
    suite_id: str
    suite_index: int
    prompt_hashes: Mapping[str, str]
    policy_contract_hash: str
    generated_before_agent_runs: bool
    contexts_per_pack: int
    context_truth: tuple[V037ContextTruth, ...]
    aliases: tuple[V037AliasTruth, ...]


@dataclass(frozen=True)
class V037PreflightResult:
    canonical_pack_id: str
    structure_present: bool
    predictive_utility: bool
    ladder_level: int | None
    research_oracle_gain: float
    confirmation_oracle_gain: float
    transfer_oracle_gain: float
    independent_identifiability: float
    identifiable: bool


@dataclass(frozen=True)
class V037SuiteBuildResult:
    suite_id: str
    run_roots: Mapping[str, str]
    encrypted_truth_path: str
    encrypted_truth_sha256: str
    public_manifest_sha256: str
    prompt_hashes: Mapping[str, str]
    preflight: tuple[V037PreflightResult, ...]
    preflight_passed: bool


PACK_DEFINITIONS = (
    V037PackDefinition("persistent_clear", True, True, "persistent-l1", 1),
    V037PackDefinition("persistent_noisy_proxy", True, True, "persistent-l2", 2),
    V037PackDefinition("persistent_delayed_history", True, True, "persistent-l3", 3),
    V037PackDefinition("persistent_compositional", True, True, "persistent-l4", 4),
    V037PackDefinition("matched_nonpersistent_clear", False, False, "persistent-l1", 1),
    V037PackDefinition("matched_nonpersistent_noisy", False, False, "persistent-l2", 2),
    V037PackDefinition("matched_nonpersistent_delayed", False, False, "persistent-l3", 3),
    V037PackDefinition("matched_nonpersistent_compositional", False, False, "persistent-l4", 4),
    V037PackDefinition("observation_routing_composition", True, True, "observation-routing"),
    V037PackDefinition("stable_structure_nonactionable", True, False, "nonactionable-structure"),
    V037PackDefinition("useful_encoding_without_structure", False, True, "encoding-only"),
    V037PackDefinition("random_routing_surface", False, False, "routing-surface"),
)

CANONICAL_FEATURES = (
    "sequence_coordinate",
    "repeated_key",
    "secondary_key",
    "primary_signal",
    "history_source",
    "heldout_attribute",
    "measurement_a",
    "measurement_b",
    "partition_hint",
    "frequency_decoy",
    "ambient_noise",
)


def build_v037_suite(
    *,
    suite_id: str,
    suite_index: int,
    output_root: Path,
    truth_root: Path,
    key: bytes,
    prompt_paths: Mapping[str, Path],
    policy_contract: Mapping[str, Any],
    contexts_per_pack: int = 3,
    rows_per_context: int = 900,
    master_seed: int = 20260827,
) -> V037SuiteBuildResult:
    """Create one immutable suite with six independently permuted run views."""

    if suite_id not in V037_SUITE_IDS or suite_index not in range(1, 5):
        raise ValueError("v0.3.7 reproducibility requires one of four preregistered suite identities")
    if contexts_per_pack < 3 or rows_per_context < 600:
        raise ValueError("aggregate promotion requires three contexts and at least 600 rows")
    if output_root.exists() or (truth_root / f"{suite_id}.manifest.enc").exists():
        raise FileExistsError("v0.3.7 suites are immutable; use a new suite identity")
    Fernet(key)
    prompt_hashes = {name: _sha256_file(path) for name, path in sorted(prompt_paths.items())}
    if set(prompt_hashes) != {"p0", "p1"}:
        raise ValueError("both frozen P0 and P1 prompts are required before suite generation")
    policy_hash = hashlib.sha256(json.dumps(policy_contract, sort_keys=True).encode()).hexdigest()

    canonical: dict[str, list[tuple[str, list[dict[str, Any]], V037ContextTruth]]] = {}
    for pack_index, definition in enumerate(PACK_DEFINITIONS, start=1):
        pack_id = f"pack-{pack_index:02d}"
        contexts: list[tuple[str, list[dict[str, Any]], V037ContextTruth]] = []
        for context_index in range(1, contexts_per_pack + 1):
            context_id = f"context-{context_index:02d}"
            seed = _derive_int(master_seed, suite_id, pack_id, context_id)
            rows = _generate_context(definition, seed=seed, count=rows_per_context)
            research_end = int(len(rows) * 0.60)
            confirmation_end = int(len(rows) * 0.80)
            research = rows[:research_end]
            confirmation = rows[research_end:confirmation_end]
            transfer = rows[confirmation_end:]
            context_truth_item = V037ContextTruth(
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
            )
            contexts.append((context_id, rows, context_truth_item))
        canonical[pack_id] = contexts

    output_root.mkdir(parents=True)
    truth_root.mkdir(parents=True, exist_ok=True)
    aliases: list[V037AliasTruth] = []
    public_hashes: list[str] = []
    for run_index, run_id in enumerate(V037_RUN_IDS):
        agent_id, sampling_seed = _parse_run_id(run_id)
        prompt_arm, policy = _latin_square_assignment(suite_index, run_index)
        run_root = output_root / "agent_views" / run_id
        run_root.mkdir(parents=True)
        prompt_target = run_root / "agent_prompt.md"
        prompt_target.write_bytes(prompt_paths[prompt_arm].read_bytes())
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
            "version": "0.3.7",
            "suite_id": suite_id,
            "run_id": run_id,
            "agent_id": agent_id,
            "sampling_seed": sampling_seed,
            "prompt_arm": prompt_arm,
            "lineage_policy": policy,
            "prompt_hash": prompt_hashes[prompt_arm],
            "policy_contract_hash": policy_hash,
            "cross_run_information": "none",
            "max_cycles_per_pack": 4,
            "null_policy": policy_contract["null_policy"],
            "confidence_fields": policy_contract["confidence_fields"],
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
    encrypted_path.write_bytes(Fernet(key).encrypt(json.dumps(asdict(suite_truth), sort_keys=True).encode()))
    os.chmod(encrypted_path, 0o600)
    preflight = preflight_v037_suite(suite_truth)
    return V037SuiteBuildResult(
        suite_id=suite_id,
        run_roots={run_id: str(output_root / "agent_views" / run_id) for run_id in V037_RUN_IDS},
        encrypted_truth_path=str(encrypted_path),
        encrypted_truth_sha256=_sha256_file(encrypted_path),
        public_manifest_sha256=hashlib.sha256("".join(sorted(public_hashes)).encode()).hexdigest(),
        prompt_hashes=prompt_hashes,
        preflight=preflight,
        preflight_passed=all(item.identifiable for item in preflight),
    )


def decrypt_v037_suite(path: Path, key: bytes) -> V037SuiteTruth:
    payload = json.loads(Fernet(key).decrypt(path.read_bytes()))
    return V037SuiteTruth(
        suite_id=str(payload["suite_id"]),
        suite_index=int(payload["suite_index"]),
        prompt_hashes={str(key): str(value) for key, value in payload["prompt_hashes"].items()},
        policy_contract_hash=str(payload["policy_contract_hash"]),
        generated_before_agent_runs=bool(payload["generated_before_agent_runs"]),
        contexts_per_pack=int(payload["contexts_per_pack"]),
        context_truth=tuple(V037ContextTruth(**item) for item in payload["context_truth"]),
        aliases=tuple(V037AliasTruth(**item) for item in payload["aliases"]),
    )


def preflight_v037_suite(
    truth: V037SuiteTruth,
    *,
    metric: Callable[[Sequence[float], Sequence[float]], float] | None = None,
) -> tuple[V037PreflightResult, ...]:
    """``metric`` defaults to :func:`_auc` (the original, binary-target behaviour). A
    regression suite passes :func:`_spearman` instead -- everything else (the gain formula,
    identifiability thresholds) is metric-scale-agnostic by construction, see
    docs/verification/v043_rossmann_regression_preregistration.md SS2.
    """

    if metric is None:
        metric = _auc
    grouped: dict[str, list[V037ContextTruth]] = {}
    for context in truth.context_truth:
        grouped.setdefault(context.canonical_pack_id, []).append(context)
    output: list[V037PreflightResult] = []
    for pack_id, contexts in sorted(grouped.items()):
        research = median(
            metric(item.research_targets, item.oracle_research_predictions)
            - metric(item.research_targets, item.control_research_predictions)
            for item in contexts
        )
        confirmation = median(
            metric(item.confirmation_targets, item.oracle_confirmation_predictions)
            - metric(item.confirmation_targets, item.control_confirmation_predictions)
            for item in contexts
        )
        transfer = median(
            metric(item.transfer_targets, item.oracle_transfer_predictions)
            - metric(item.transfer_targets, item.control_transfer_predictions)
            for item in contexts
        )
        first = contexts[0]
        independent = median(item.independent_identifiability for item in contexts)
        if first.structure_present and first.predictive_utility:
            identifiable = research > 0.02 and confirmation > 0 and transfer > 0 and independent > 0.05
        elif first.structure_present:
            identifiable = independent > 0.10 and abs(transfer) < 0.02
        elif first.predictive_utility:
            identifiable = abs(independent) < 0.05
        else:
            identifiable = abs(research) < 1e-12 and abs(transfer) < 1e-12
        output.append(
            V037PreflightResult(
                canonical_pack_id=pack_id,
                structure_present=first.structure_present,
                predictive_utility=first.predictive_utility,
                ladder_level=first.ladder_level,
                research_oracle_gain=research,
                confirmation_oracle_gain=confirmation,
                transfer_oracle_gain=transfer,
                independent_identifiability=independent,
                identifiable=identifiable,
            )
        )
    return tuple(output)


def audit_v037_agent_view(root: Path) -> tuple[str, ...]:
    forbidden = (
        "structure_present",
        "predictive_utility",
        "generator_seed",
        "confirmation_targets",
        "transfer_targets",
        "persistent_clear",
        "persistent_noisy_proxy",
        "persistent_delayed_history",
        "persistent_compositional",
        "matched_nonpersistent",
        "observation_routing_composition",
        "stable_structure_nonactionable",
        "useful_encoding_without_structure",
        "random_routing_surface",
    )
    findings: list[str] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        text = path.read_text(errors="ignore")
        findings.extend(f"{path.relative_to(root)}:{token}" for token in forbidden if token in text)
    return tuple(findings)


def _latin_square_assignment(suite_index: int, run_index: int) -> tuple[str, str]:
    combinations = (
        ("p0", "deterministic_best"),
        ("p0", "posterior_commit"),
        ("p0", "two_hit_maturation"),
        ("p1", "deterministic_best"),
        ("p1", "posterior_commit"),
        ("p1", "two_hit_maturation"),
    )
    return combinations[(run_index + suite_index - 1) % len(combinations)]


def _generate_context(definition: V037PackDefinition, *, seed: int, count: int) -> list[dict[str, Any]]:
    generator = random.Random(seed)
    unit_count = 48
    unit_effect = {unit: generator.gauss(0, 1.0) for unit in range(unit_count)}
    history: dict[int, list[float]] = {unit: [] for unit in range(unit_count)}
    rows: list[dict[str, Any]] = []
    for row_id in range(count):
        time = row_id / max(count - 1, 1)
        true_unit = (row_id * 17 + generator.randrange(13)) % unit_count
        signal = generator.gauss(0, 1)
        source = generator.gauss(0, 1)
        route = generator.randrange(2)
        pattern = (row_id + generator.randrange(4)) % 3
        measure_a = None if pattern == 1 else generator.gauss(0, 1)
        measure_b = None if pattern == 2 else generator.gauss(0, 1)
        missing_count = int(measure_a is None) + int(measure_b is None)
        heldout = unit_effect[true_unit] + generator.gauss(0, 0.32)
        frequency_decoy = math.log1p(true_unit % 8)
        repeated_key: int | None = true_unit
        secondary_key: int | None = (true_unit * 7 + 3) % 53
        base = 0.95 * signal + 0.10 * generator.gauss(0, 1)
        structure = 0.0
        independent = 0.0
        if definition.ladder_level == 1:
            if definition.structure_present:
                base = 0.35 * signal
                structure = 1.9 * unit_effect[true_unit]
                independent = unit_effect[true_unit]
            else:
                base = 0.95 * signal + 0.18 * frequency_decoy
        elif definition.ladder_level == 2:
            if generator.random() < 0.25:
                repeated_key = None
            elif generator.random() < 0.20:
                repeated_key = generator.randrange(unit_count)
            if generator.random() < 0.18:
                secondary_key = generator.randrange(53)
            if definition.structure_present:
                base = 0.45 * signal + 0.12 * frequency_decoy
                structure = 1.45 * unit_effect[true_unit]
                independent = unit_effect[true_unit]
            else:
                base = 0.95 * signal + 0.25 * frequency_decoy
        elif definition.ladder_level == 3:
            past = history[true_unit][-5:]
            delayed = sum(past) / len(past) if past else 0.0
            if definition.structure_present:
                base = 0.45 * signal
                structure = 1.55 * delayed
                independent = delayed
            else:
                base = 0.95 * signal + 0.12 * frequency_decoy
        elif definition.ladder_level == 4:
            if generator.random() < 0.18:
                repeated_key = None
            drifted = unit_effect[true_unit] * (1.35 if time < 0.55 else -0.75)
            if definition.structure_present:
                base = 0.40 * signal + 0.35 * frequency_decoy + 0.25 * time
                structure = 1.40 * drifted
                independent = drifted
            else:
                base = 0.90 * signal + 0.35 * frequency_decoy + 0.25 * time
        elif definition.family == "observation_routing_composition":
            base = 0.15 * signal + 0.12 * route
            structure = ({0: 1.7, 1: -1.6, 2: 0.55}[pattern] + (0.5 if route else -0.4)) * signal
            independent = float(pattern == route)
        elif definition.family == "stable_structure_nonactionable":
            base = 1.0 * signal
            independent = unit_effect[true_unit]
        elif definition.family == "useful_encoding_without_structure":
            base = 0.35 * signal + 1.25 * math.sin(signal * 1.8) + 0.35 * missing_count
        elif definition.family == "random_routing_surface":
            base = 1.0 * signal + 0.25 * route
        else:
            raise ValueError(f"unknown v0.3.7 family: {definition.family}")
        logit = base + structure
        target = int(generator.random() < _sigmoid(logit))
        rows.append(
            {
                "row_id": row_id,
                "sequence_coordinate": time,
                "repeated_key": repeated_key,
                "secondary_key": secondary_key,
                "primary_signal": signal,
                "history_source": source,
                "heldout_attribute": heldout,
                "measurement_a": measure_a,
                "measurement_b": measure_b,
                "partition_hint": route,
                "frequency_decoy": frequency_decoy,
                "ambient_noise": generator.gauss(0, 1),
                "target": target,
                "_oracle": _sigmoid(logit),
                "_control": _sigmoid(base),
                "_independent": independent,
            }
        )
        history[true_unit].append(source)
    return rows


def _independent_identifiability(definition: V037PackDefinition) -> float:
    if definition.structure_present:
        return 0.32 if definition.family == "stable_structure_nonactionable" else 0.24
    return 0.0


def _agent_rows(
    rows: Sequence[Mapping[str, Any]],
    column_map: Mapping[str, str],
    *,
    include_target: bool,
    seed: int,
) -> list[dict[str, Any]]:
    visible: list[dict[str, Any]] = []
    for row in rows:
        item = {column_map[column]: row[column] for column in CANONICAL_FEATURES}
        item["row_id"] = row["row_id"]
        if include_target:
            item["target"] = row["target"]
        visible.append(item)
    random.Random(seed).shuffle(visible)
    return visible


def _visible_column_map(key: bytes, suite_id: str, run_id: str, pack_id: str) -> dict[str, str]:
    output: dict[str, str] = {}
    for index, canonical in enumerate(CANONICAL_FEATURES):
        payload = f"{suite_id}:{run_id}:{pack_id}:{canonical}".encode()
        digest = hmac.new(key, payload, hashlib.sha256).hexdigest()
        output[canonical] = f"x_{index:02d}_{digest[:7]}"
    return output


def _parse_run_id(run_id: str) -> tuple[str, int]:
    agent, seed = run_id.rsplit("-s", 1)
    return agent, int(seed)


def _opaque_id(key: bytes, *parts: str) -> str:
    return f"opaque-{hmac.new(key, ':'.join(parts).encode(), hashlib.sha256).hexdigest()[:20]}"


def _derive_int(seed: int, *parts: str) -> int:
    return int.from_bytes(hashlib.sha256((f"{seed}:" + ":".join(parts)).encode()).digest()[:8], "big")


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _auc(targets: Sequence[float], predictions: Sequence[float]) -> float:
    if len(targets) != len(predictions) or len(targets) == 0:
        raise ValueError("AUC inputs must be non-empty and aligned")
    positives = sum(targets)
    negatives = len(targets) - positives
    if not positives or not negatives:
        return 0.5
    ordered = sorted(zip(predictions, targets, strict=True), key=lambda item: item[0])
    rank_sum = 0.0
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and ordered[end][0] == ordered[start][0]:
            end += 1
        rank_sum += (start + 1 + end) / 2 * sum(target for _, target in ordered[start:end])
        start = end
    return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def _rank(values: Sequence[float]) -> list[float]:
    ordered = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[start]]:
            end += 1
        average_rank = (start + 1 + end) / 2
        for position in range(start, end):
            ranks[ordered[position]] = average_rank
        start = end
    return ranks


def _spearman(targets: Sequence[float], predictions: Sequence[float]) -> float:
    """Spearman rank correlation, for regression suites' identifiability/gain metric.

    Companion to :func:`_auc` (which assumes a binary target and is not meaningful for a
    continuous one). Ties are handled via average ranks, matching ``_auc``'s tie handling.
    Degenerate case: a constant ``predictions`` series (e.g. the capacity-matched control,
    which always predicts the training-segment mean) makes the correlation mathematically
    undefined (zero variance -> 0/0). ``_auc`` resolves its own degenerate case (no positives
    or no negatives) to the chance-level value ``0.5``; by the same logic this returns the
    chance-level value ``0.0`` rather than raising or returning NaN.
    """

    if len(targets) != len(predictions) or len(targets) == 0:
        raise ValueError("correlation inputs must be non-empty and aligned")
    target_ranks = _rank(list(targets))
    prediction_ranks = _rank(list(predictions))
    n = len(target_ranks)
    target_mean = sum(target_ranks) / n
    prediction_mean = sum(prediction_ranks) / n
    covariance = sum(
        (t - target_mean) * (p - prediction_mean) for t, p in zip(target_ranks, prediction_ranks, strict=True)
    )
    target_variance = sum((t - target_mean) ** 2 for t in target_ranks)
    prediction_variance = sum((p - prediction_mean) ** 2 for p in prediction_ranks)
    if target_variance == 0 or prediction_variance == 0:
        return 0.0
    return covariance / math.sqrt(target_variance * prediction_variance)


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1 / (1 + math.exp(-value))
    exponent = math.exp(value)
    return exponent / (1 + exponent)
