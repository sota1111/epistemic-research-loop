"""Blind v0.3.6 structure packs for real-agent qualification.

The builder writes two disjoint products:

* agent views containing labelled research rows and unlabelled sealed rows;
* a Fernet-encrypted controller manifest containing family, polarity, labels,
  and reference-oracle predictions.

The agent runtime consumes only ``agent_packet.json`` below its assigned view.
The generator and decryption key are not part of that runtime contract.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import random
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import Any

from cryptography.fernet import Fernet

V036_DEVELOPMENT_SUITE_ID = "v036-development-01"
V036_QUALIFICATION_SUITE_ID = "v036-qualification-01"
DEFAULT_AGENTS = ("agent-01", "agent-02", "agent-03")


@dataclass(frozen=True)
class PackDefinition:
    family: str
    structure_present: bool
    matched_pair: str


@dataclass(frozen=True)
class ContextTruth:
    canonical_pack_id: str
    canonical_context_id: str
    family: str
    structure_present: bool
    generator_seed: int
    sealed_targets: tuple[int, ...]
    research_targets: tuple[int, ...]
    oracle_research_predictions: tuple[float, ...]
    control_research_predictions: tuple[float, ...]
    oracle_sealed_predictions: tuple[float, ...]
    control_sealed_predictions: tuple[float, ...]


@dataclass(frozen=True)
class AgentAliasTruth:
    agent_id: str
    opaque_pack_id: str
    opaque_context_id: str
    canonical_pack_id: str
    canonical_context_id: str
    canonical_to_visible_columns: Mapping[str, str]


@dataclass(frozen=True)
class SuiteTruth:
    suite_id: str
    suite_kind: str
    prompt_hash: str
    generated_after_prompt_freeze: bool
    contexts_per_pack: int
    context_truth: tuple[ContextTruth, ...]
    aliases: tuple[AgentAliasTruth, ...]


@dataclass(frozen=True)
class PreflightPackResult:
    canonical_pack_id: str
    structure_present: bool
    research_median_oracle_gain: float
    sealed_median_oracle_gain: float
    direction_stable: bool
    identifiable: bool


@dataclass(frozen=True)
class SuiteBuildResult:
    suite_id: str
    suite_kind: str
    agent_roots: Mapping[str, str]
    encrypted_truth_path: str
    encrypted_truth_sha256: str
    public_manifest_sha256: str
    preflight: tuple[PreflightPackResult, ...]
    preflight_passed: bool


PACK_DEFINITIONS = (
    PackDefinition("persistent_unit_dependence", True, "unit_surface"),
    PackDefinition("changing_temporal_relation", True, "time_surface"),
    PackDefinition("observation_regime_interaction", True, "observation_surface"),
    PackDefinition("conditional_mechanism_composition", True, "routing_surface"),
    PackDefinition("unit_frequency_only", False, "unit_surface"),
    PackDefinition("time_additive_only", False, "time_surface"),
    PackDefinition("missingness_additive_only", False, "observation_surface"),
    PackDefinition("routing_additive_only", False, "routing_surface"),
)

CANONICAL_FEATURES = (
    "sequence_coordinate",
    "repeated_key",
    "primary_signal",
    "heldout_attribute",
    "measurement_a",
    "measurement_b",
    "partition_hint",
    "ambient_noise_a",
    "ambient_noise_b",
)


def build_blind_structure_suite(
    *,
    suite_id: str,
    suite_kind: str,
    output_root: Path,
    truth_root: Path,
    key: bytes,
    prompt_hash: str,
    agents: Sequence[str] = DEFAULT_AGENTS,
    positive_packs: int = 4,
    negative_packs: int = 4,
    contexts_per_pack: int = 3,
    rows_per_context: int = 1200,
    master_seed: int = 20260827,
) -> SuiteBuildResult:
    """Build frozen agent views and an encrypted controller-only truth manifest."""

    if positive_packs != 4 or negative_packs != 4:
        raise ValueError("the v0.3.6 pilot requires four positive and four negative packs")
    if contexts_per_pack < 3:
        raise ValueError("aggregate promotion requires at least three contexts")
    if len(set(agents)) != len(agents) or len(agents) != 3:
        raise ValueError("the v0.3.6 pilot requires three unique agents")
    if rows_per_context < 600:
        raise ValueError("identifiability preflight requires at least 600 rows per context")
    if not suite_id.strip() or suite_kind not in {"development", "qualification"}:
        raise ValueError("suite identity and kind are required")
    Fernet(key)  # validate before writing any artifact

    output_root.mkdir(parents=True, exist_ok=True)
    truth_root.mkdir(parents=True, exist_ok=True)
    canonical: dict[str, list[tuple[str, list[dict[str, Any]], list[dict[str, Any]], ContextTruth]]] = {}
    for pack_index, definition in enumerate(PACK_DEFINITIONS, start=1):
        canonical_pack_id = f"pack-{pack_index:02d}"
        contexts: list[tuple[str, list[dict[str, Any]], list[dict[str, Any]], ContextTruth]] = []
        for context_index in range(1, contexts_per_pack + 1):
            context_id = f"context-{context_index:02d}"
            seed = _derive_int(master_seed, suite_id, canonical_pack_id, context_id)
            rows = _generate_context(definition, seed=seed, count=rows_per_context)
            split = int(len(rows) * 0.70)
            research, sealed = rows[:split], rows[split:]
            context_truth_item = ContextTruth(
                canonical_pack_id=canonical_pack_id,
                canonical_context_id=context_id,
                family=definition.family,
                structure_present=definition.structure_present,
                generator_seed=seed,
                sealed_targets=tuple(int(item["target"]) for item in sealed),
                research_targets=tuple(int(item["target"]) for item in research),
                oracle_research_predictions=tuple(float(item.pop("_oracle")) for item in research),
                control_research_predictions=tuple(float(item.pop("_control")) for item in research),
                oracle_sealed_predictions=tuple(float(item.pop("_oracle")) for item in sealed),
                control_sealed_predictions=tuple(float(item.pop("_control")) for item in sealed),
            )
            contexts.append((context_id, research, sealed, context_truth_item))
        canonical[canonical_pack_id] = contexts

    aliases: list[AgentAliasTruth] = []
    context_truth = tuple(item[3] for contexts in canonical.values() for item in contexts)
    public_hashes: list[str] = []
    for agent_id in agents:
        agent_root = output_root / "agent_views" / agent_id
        agent_root.mkdir(parents=True, exist_ok=True)
        packet_packs: list[dict[str, Any]] = []
        pack_order = list(canonical)
        random.Random(_derive_int(master_seed, suite_id, agent_id, "pack-order")).shuffle(pack_order)
        for canonical_pack_id in pack_order:
            opaque_pack_id = _opaque_id(key, suite_id, agent_id, canonical_pack_id, "pack")
            pack_root = agent_root / opaque_pack_id
            pack_root.mkdir(parents=True, exist_ok=True)
            context_entries: list[dict[str, Any]] = []
            column_map = _visible_column_map(key, suite_id, agent_id, canonical_pack_id)
            context_order = list(canonical[canonical_pack_id])
            random.Random(_derive_int(master_seed, suite_id, agent_id, canonical_pack_id)).shuffle(context_order)
            for canonical_context_id, research, sealed, _truth in context_order:
                opaque_context_id = _opaque_id(
                    key,
                    suite_id,
                    agent_id,
                    canonical_pack_id,
                    canonical_context_id,
                )
                research_rows = _agent_rows(
                    research,
                    column_map,
                    include_target=True,
                    seed=_derive_int(master_seed, agent_id, opaque_context_id, "research"),
                )
                sealed_rows = _agent_rows(
                    sealed,
                    column_map,
                    include_target=False,
                    seed=_derive_int(master_seed, agent_id, opaque_context_id, "sealed"),
                )
                research_name = f"{opaque_context_id}.research.json"
                sealed_name = f"{opaque_context_id}.sealed.json"
                _write_json(pack_root / research_name, research_rows)
                _write_json(pack_root / sealed_name, sealed_rows)
                aliases.append(
                    AgentAliasTruth(
                        agent_id=agent_id,
                        opaque_pack_id=opaque_pack_id,
                        opaque_context_id=opaque_context_id,
                        canonical_pack_id=canonical_pack_id,
                        canonical_context_id=canonical_context_id,
                        canonical_to_visible_columns=column_map,
                    )
                )
                context_entries.append(
                    {
                        "opaque_context_id": opaque_context_id,
                        "research_file": str((Path(opaque_pack_id) / research_name).as_posix()),
                        "sealed_file": str((Path(opaque_pack_id) / sealed_name).as_posix()),
                        "research_rows": len(research_rows),
                        "sealed_rows": len(sealed_rows),
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
            "version": "0.3.6",
            "suite_id": suite_id,
            "agent_id": agent_id,
            "metric": "roc_auc",
            "max_adaptive_cycles_per_pack": 4,
            "fixed_niche": False,
            "cross_agent_information": "none",
            "packs": packet_packs,
            "prompt_file": "v036_agent_prompt.md",
            "submission_contract_file": "v036_submission_contract.json",
        }
        _write_json(agent_root / "agent_packet.json", packet)
        public_hashes.append(_sha256_file(agent_root / "agent_packet.json"))

    suite_truth = SuiteTruth(
        suite_id=suite_id,
        suite_kind=suite_kind,
        prompt_hash=prompt_hash,
        generated_after_prompt_freeze=True,
        contexts_per_pack=contexts_per_pack,
        context_truth=context_truth,
        aliases=tuple(aliases),
    )
    encrypted_path = truth_root / f"{suite_id}.manifest.enc"
    plaintext = json.dumps(asdict(suite_truth), sort_keys=True, separators=(",", ":")).encode()
    encrypted_path.write_bytes(Fernet(key).encrypt(plaintext))
    os.chmod(encrypted_path, 0o600)
    preflight = run_identifiability_preflight(suite_truth)
    return SuiteBuildResult(
        suite_id=suite_id,
        suite_kind=suite_kind,
        agent_roots={agent: str(output_root / "agent_views" / agent) for agent in agents},
        encrypted_truth_path=str(encrypted_path),
        encrypted_truth_sha256=_sha256_file(encrypted_path),
        public_manifest_sha256=hashlib.sha256("".join(sorted(public_hashes)).encode()).hexdigest(),
        preflight=preflight,
        preflight_passed=all(item.identifiable for item in preflight),
    )


def decrypt_suite_truth(path: Path, key: bytes) -> SuiteTruth:
    payload = json.loads(Fernet(key).decrypt(path.read_bytes()))
    return SuiteTruth(
        suite_id=str(payload["suite_id"]),
        suite_kind=str(payload["suite_kind"]),
        prompt_hash=str(payload["prompt_hash"]),
        generated_after_prompt_freeze=bool(payload["generated_after_prompt_freeze"]),
        contexts_per_pack=int(payload["contexts_per_pack"]),
        context_truth=tuple(ContextTruth(**item) for item in payload["context_truth"]),
        aliases=tuple(AgentAliasTruth(**item) for item in payload["aliases"]),
    )


def run_identifiability_preflight(
    truth: SuiteTruth,
    *,
    minimum_positive_gain: float = 0.03,
) -> tuple[PreflightPackResult, ...]:
    grouped: dict[str, list[ContextTruth]] = {}
    for context in truth.context_truth:
        grouped.setdefault(context.canonical_pack_id, []).append(context)
    output: list[PreflightPackResult] = []
    for pack_id, contexts in sorted(grouped.items()):
        research_gains = [
            _auc(item.research_targets, item.oracle_research_predictions)
            - _auc(item.research_targets, item.control_research_predictions)
            for item in contexts
        ]
        sealed_gains = [
            _auc(item.sealed_targets, item.oracle_sealed_predictions)
            - _auc(item.sealed_targets, item.control_sealed_predictions)
            for item in contexts
        ]
        present = contexts[0].structure_present
        if present:
            stable = sum(value > 0 for value in sealed_gains) >= 2 and min(sealed_gains) > -0.01
            identifiable = median(research_gains) >= minimum_positive_gain and median(sealed_gains) > 0 and stable
        else:
            stable = max(abs(value) for value in sealed_gains) <= 1e-12
            identifiable = stable
        output.append(
            PreflightPackResult(
                canonical_pack_id=pack_id,
                structure_present=present,
                research_median_oracle_gain=median(research_gains),
                sealed_median_oracle_gain=median(sealed_gains),
                direction_stable=stable,
                identifiable=identifiable,
            )
        )
    return tuple(output)


def audit_agent_view(root: Path) -> tuple[str, ...]:
    """Return any controller-only token found in an agent-visible tree."""

    forbidden = (
        "structure_present",
        "generator_seed",
        "sealed_targets",
        "expected_operator",
        "family_label",
        "persistent_unit_dependence",
        "changing_temporal_relation",
        "observation_regime_interaction",
        "conditional_mechanism_composition",
        "unit_frequency_only",
        "time_additive_only",
        "missingness_additive_only",
        "routing_additive_only",
    )
    findings: list[str] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        text = path.read_text(errors="ignore")
        for token in forbidden:
            if token in text:
                findings.append(f"{path.relative_to(root)}:{token}")
    return tuple(findings)


def _generate_context(definition: PackDefinition, *, seed: int, count: int) -> list[dict[str, Any]]:
    generator = random.Random(seed)
    unit_effect = {unit: generator.gauss(0, 0.95) for unit in range(44)}
    rows: list[dict[str, Any]] = []
    for row_id in range(count):
        time = row_id / max(count - 1, 1)
        unit = (row_id * 19 + generator.randrange(11)) % 44
        signal = generator.gauss(0, 1)
        route = generator.randrange(2)
        pattern = (row_id + generator.randrange(3)) % 3
        measure_a = None if pattern == 1 else generator.gauss(0, 1)
        measure_b = None if pattern == 2 else generator.gauss(0, 1)
        missing_count = int(measure_a is None) + int(measure_b is None)
        heldout = unit_effect[unit] + generator.gauss(0, 0.35)
        noise_a = generator.gauss(0, 1)
        noise_b = generator.gauss(0, 1)
        base = 0.75 * signal + 0.12 * noise_a
        structure = 0.0
        if definition.family == "persistent_unit_dependence":
            base = 0.40 * signal
            structure = 1.75 * unit_effect[unit]
        elif definition.family == "unit_frequency_only":
            base += 0.22 * math.log1p(unit % 7)
        elif definition.family == "changing_temporal_relation":
            base = 0.15 * signal + 0.18 * time
            structure = (-1.7 + 3.9 * time) * signal
        elif definition.family == "time_additive_only":
            base = 1.20 * signal + 0.65 * time
        elif definition.family == "observation_regime_interaction":
            base = 0.15 * signal + 0.18 * missing_count
            structure = {0: 0.85, 1: 2.35, 2: -2.10}[pattern] * signal
        elif definition.family == "missingness_additive_only":
            base = 1.15 * signal + 0.90 * missing_count
        elif definition.family == "conditional_mechanism_composition":
            base = 0.10 * signal + 0.10 * route + 0.08 * time
            structure = (-2.2 if route == 0 else 2.35) * signal + 0.65 * route * (time - 0.5)
        elif definition.family == "routing_additive_only":
            base = 1.20 * signal + 0.48 * route + 0.12 * time
        else:
            raise ValueError(f"unknown pack definition: {definition.family}")
        logit = base + structure
        target = int(generator.random() < _sigmoid(logit))
        rows.append(
            {
                "row_id": row_id,
                "sequence_coordinate": time,
                "repeated_key": unit,
                "primary_signal": signal,
                "heldout_attribute": heldout,
                "measurement_a": measure_a,
                "measurement_b": measure_b,
                "partition_hint": route,
                "ambient_noise_a": noise_a,
                "ambient_noise_b": noise_b,
                "target": target,
                "_oracle": _sigmoid(logit),
                "_control": _sigmoid(base),
            }
        )
    return rows


def _agent_rows(
    rows: Sequence[Mapping[str, Any]],
    column_map: Mapping[str, str],
    *,
    include_target: bool,
    seed: int,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        visible = {column_map[key]: row[key] for key in CANONICAL_FEATURES}
        visible["row_id"] = row["row_id"]
        if include_target:
            visible["target"] = row["target"]
        output.append(visible)
    random.Random(seed).shuffle(output)
    return output


def _visible_column_map(key: bytes, suite_id: str, agent_id: str, pack_id: str) -> dict[str, str]:
    output: dict[str, str] = {}
    for index, canonical in enumerate(CANONICAL_FEATURES):
        digest = hmac.new(key, f"{suite_id}:{agent_id}:{pack_id}:{canonical}".encode(), hashlib.sha256).hexdigest()
        output[canonical] = f"v_{index:02d}_{digest[:7]}"
    return output


def _opaque_id(key: bytes, *parts: str) -> str:
    digest = hmac.new(key, ":".join(parts).encode(), hashlib.sha256).hexdigest()
    return f"opaque-{digest[:20]}"


def _derive_int(seed: int, *parts: str) -> int:
    payload = f"{seed}:" + ":".join(parts)
    return int.from_bytes(hashlib.sha256(payload.encode()).digest()[:8], "big")


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _auc(targets: Sequence[int], predictions: Sequence[float]) -> float:
    if len(targets) != len(predictions) or not targets:
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
        average_rank = (start + 1 + end) / 2
        rank_sum += average_rank * sum(target for _, target in ordered[start:end])
        start = end
    return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1 / (1 + math.exp(-value))
    exponent = math.exp(value)
    return exponent / (1 + exponent)
