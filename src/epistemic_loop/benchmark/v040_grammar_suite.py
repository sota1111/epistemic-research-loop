"""v0.4.0 Track-A suites: persistent-heavy pack set plus grammar-composed structures.

Two departures from the v0.3.x suites, per the v0.4.0 policy:

1. **Structure grammar.** Two of the seven positive packs carry structures composed by a
   motif grammar (entity effects, delayed history, regime flips, cross-key links, path
   decay, routed signals). The concrete instance is sampled from the suite's master seed
   and accepted only if an identifiability preflight passes, so the suite designer does
   not hand-pick — or know in advance — the composed structure's shape.
2. **Configuration slots.** The six run views of a suite are execution-configuration
   slots (model x scaffold), not agent identities. The prompt arm can differ per slot;
   the lineage policy is fixed to posterior-commit for every slot.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

from epistemic_loop.benchmark.v037_repro_suite import (
    V037_RUN_IDS,
    V037AliasTruth,
    V037ContextTruth,
    V037PackDefinition,
    V037SuiteBuildResult,
    V037SuiteTruth,
    _agent_rows,
    _auc,
    _derive_int,
    _generate_context,
    _opaque_id,
    _parse_run_id,
    _sha256_file,
    _sigmoid,
    _visible_column_map,
    _write_json,
    preflight_v037_suite,
)
from epistemic_loop.controller.v037_agent import MAX_CYCLES_PER_PACK

V040_GEN1_SUITE_IDS = tuple(f"v040-genA-g{index:02d}" for index in range(1, 5))
V040_GEN1_MASTER_SEED = 20260910
V040_RUN_IDS = V037_RUN_IDS
V040_LINEAGE_POLICY = "posterior_commit"

#: Preregistered-run exclusions recorded before unblinding (deviation entry in
#: ``docs/v040_gen1_preregistration.json``). Keys are (suite_id, run_id) pairs that the
#: lock and finalize stages must treat as absent, with the recorded reason. The agent
#: view of an excluded pair still exists and is still blindness-audited.
V040_GEN1_EXCLUDED_RUNS: Mapping[tuple[str, str], str] = {}

#: Generation-1 execution configurations, one per run-view slot. The slot ids reuse the
#: v0.3.x run-id vocabulary so the locked evaluation (which aggregates per agent x seed)
#: yields per-configuration aggregates unchanged.
V040_GEN1_CONFIGS: Mapping[str, Mapping[str, str]] = {
    "agent-01-s17": {"config_id": "C1", "cli": "claude", "model": "claude-fable-5", "prompt_arm": "p1"},
    "agent-01-s42": {"config_id": "C2", "cli": "claude", "model": "claude-fable-5", "prompt_arm": "p2"},
    "agent-02-s17": {"config_id": "C3", "cli": "claude", "model": "claude-opus-5", "prompt_arm": "p1"},
    "agent-02-s42": {"config_id": "C4", "cli": "claude", "model": "claude-sonnet-5", "prompt_arm": "p2"},
    "agent-03-s17": {"config_id": "C5", "cli": "codex", "model": "gpt-5.6-sol", "prompt_arm": "p1"},
    "agent-03-s42": {"config_id": "C6", "cli": "codex", "model": "gpt-5.6-terra", "prompt_arm": "p1"},
}

#: Independent side-probe: codex sol reasoning-effort ablation (deferred_to_generation_2 item
#: in docs/v040_gen1_preregistration.json). Single-intervention design -- CLI, model, and
#: prompt arm are held fixed at generation 1's C5 baseline; only reasoning_effort varies.
#: New suite identities and master seed (generation 1's suites are already unblinded). Six
#: suite instances: policy Sec 3.2's own "6-8 run" recommendation, now that
#: evaluate_v037_runs's suite count is an explicit parameter rather than hardcoded to 4
#: (see docs/v040_sol_effort_ablation_preregistration.json revision note; the first 4 were
#: originally built and locked as 4-only, corrected before any truth was opened).
V040_SOL_ABLATION_SUITE_IDS = tuple(f"v040-solE-b{index:02d}" for index in range(1, 7))
V040_SOL_ABLATION_MASTER_SEED = 20260915
V040_SOL_ABLATION_CONFIGS: Mapping[str, Mapping[str, str]] = {
    "agent-01-s17": {
        "config_id": "S-low",
        "cli": "codex",
        "model": "gpt-5.6-sol",
        "prompt_arm": "p1",
        "reasoning_effort": "low",
    },
    "agent-01-s42": {
        "config_id": "S-medium",
        "cli": "codex",
        "model": "gpt-5.6-sol",
        "prompt_arm": "p1",
        "reasoning_effort": "medium",
    },
    "agent-02-s17": {
        "config_id": "S-high",
        "cli": "codex",
        "model": "gpt-5.6-sol",
        "prompt_arm": "p1",
        "reasoning_effort": "high",
    },
    "agent-02-s42": {
        "config_id": "S-xhigh",
        "cli": "codex",
        "model": "gpt-5.6-sol",
        "prompt_arm": "p1",
        "reasoning_effort": "xhigh",
    },
}
V040_SOL_ABLATION_RUN_IDS = tuple(V040_SOL_ABLATION_CONFIGS)

#: Independent side-probe: Opus + Sol scaffold-ladder screen (Stage 1 of the "diversity from
#: procedure, not architecture" design -- docs/v040_scaffold_ladder_preregistration.json).
#: Single-intervention design -- CLI, model, reasoning effort, and cycle budget are held fixed
#: (sol at xhigh, matching generation 1's C5 and this ablation's not-yet-concluded default);
#: only the prompt scaffold (P1 baseline / P2 hypothesis-enumeration / P3 self-critique) varies,
#: crossed with the two models. A screening stage (4 replicates): large, easily-detected effects
#: are the target (e.g. P1->P2 already produced a 2.5x swing in generation 1), not precise
#: estimation: this is intended to identify which scaffold(s) merit generation-2-scale (6-8
#: replicate) follow-up, not to confirm one on its own.
V040_SCAFFOLD_LADDER_SUITE_IDS = tuple(f"v040-scaf-c{index:02d}" for index in range(1, 5))
V040_SCAFFOLD_LADDER_MASTER_SEED = 20260920
V040_SCAFFOLD_LADDER_CONFIGS: Mapping[str, Mapping[str, str]] = {
    "agent-01-s17": {"config_id": "L-opus-P1", "cli": "claude", "model": "claude-opus-5", "prompt_arm": "p1"},
    "agent-01-s42": {"config_id": "L-opus-P2", "cli": "claude", "model": "claude-opus-5", "prompt_arm": "p2"},
    "agent-01-s93": {"config_id": "L-opus-P3", "cli": "claude", "model": "claude-opus-5", "prompt_arm": "p3"},
    "agent-02-s17": {
        "config_id": "L-sol-P1",
        "cli": "codex",
        "model": "gpt-5.6-sol",
        "prompt_arm": "p1",
        "reasoning_effort": "xhigh",
    },
    "agent-02-s42": {
        "config_id": "L-sol-P2",
        "cli": "codex",
        "model": "gpt-5.6-sol",
        "prompt_arm": "p2",
        "reasoning_effort": "xhigh",
    },
    "agent-02-s93": {
        "config_id": "L-sol-P3",
        "cli": "codex",
        "model": "gpt-5.6-sol",
        "prompt_arm": "p3",
        "reasoning_effort": "xhigh",
    },
}
V040_SCAFFOLD_LADDER_RUN_IDS = tuple(V040_SCAFFOLD_LADDER_CONFIGS)

#: Independent side-probe: Stage 2 confirmatory follow-up on the scaffold-ladder screen's three
#: most information-rich cells (docs/v040_scaffold_ladder_stage2_preregistration.json). Not a
#: repeat of the sol reasoning-effort ablation (already have 6 clean replicates of sol x P1 x
#: xhigh from that study); this targets what Stage 1 could not resolve at n=4: does Opus x P3's
#: ~3x hypothesis-diversity boost reproduce, does Sol x P3's single-suite false-promotion spike
#: recur, and does persistent_delayed_history (0 discoveries across 88 runs so far,
#: docs/v040_discovery_ledger.md) finally break under any of these.
V040_SCAFFOLD_STAGE2_SUITE_IDS = tuple(f"v040-scaf2-d{index:02d}" for index in range(1, 7))
V040_SCAFFOLD_STAGE2_MASTER_SEED = 20260929
V040_SCAFFOLD_STAGE2_CONFIGS: Mapping[str, Mapping[str, str]] = {
    "agent-01-s17": {"config_id": "T2-opus-P1", "cli": "claude", "model": "claude-opus-5", "prompt_arm": "p1"},
    "agent-01-s93": {"config_id": "T2-opus-P3", "cli": "claude", "model": "claude-opus-5", "prompt_arm": "p3"},
    "agent-02-s93": {
        "config_id": "T2-sol-P3",
        "cli": "codex",
        "model": "gpt-5.6-sol",
        "prompt_arm": "p3",
        "reasoning_effort": "xhigh",
    },
}
V040_SCAFFOLD_STAGE2_RUN_IDS = tuple(V040_SCAFFOLD_STAGE2_CONFIGS)

#: Independent side-probe: cycle-budget ablation (4 -> 8), targeting persistent_delayed_history
#: (0/88 discoveries across every prior v0.4.0 study, docs/v040_discovery_ledger.md). Only the
#: cycle=8 arm is executed; each configuration's cycle=4 baseline is read from prior studies
#: (generation 1 + Stage 1 for opus x P1, the sol-effort ablation's xhigh for sol x P1 x xhigh).
#: See docs/v040_cycle_budget_ablation_preregistration.json.
V040_CYCLE8_SUITE_IDS = tuple(f"v040-cyc8-e{index:02d}" for index in range(1, 7))
V040_CYCLE8_MASTER_SEED = 20260929101
V040_CYCLE8_MAX_CYCLES_PER_PACK = 8
V040_CYCLE8_CONFIGS: Mapping[str, Mapping[str, str]] = {
    "agent-01-s17": {"config_id": "K8-opus-P1", "cli": "claude", "model": "claude-opus-5", "prompt_arm": "p1c8"},
    "agent-02-s17": {
        "config_id": "K8-sol-P1",
        "cli": "codex",
        "model": "gpt-5.6-sol",
        "prompt_arm": "p1c8",
        "reasoning_effort": "xhigh",
    },
}
V040_CYCLE8_RUN_IDS = tuple(V040_CYCLE8_CONFIGS)

GRAMMAR_MOTIFS = (
    "entity_effect",
    "delayed_history",
    "regime_flip",
    "cross_key_link",
    "path_decay",
    "routed_signal",
)

V040_PACK_PLAN: tuple[tuple[V037PackDefinition, str], ...] = (
    (V037PackDefinition("persistent_clear", True, True, "persistent-l1", 1), "v037"),
    (V037PackDefinition("persistent_noisy_proxy", True, True, "persistent-l2", 2), "v037"),
    (V037PackDefinition("persistent_delayed_history", True, True, "persistent-l3", 3), "v037"),
    (V037PackDefinition("persistent_compositional", True, True, "persistent-l4", 4), "v037"),
    (V037PackDefinition("matched_nonpersistent_clear", False, False, "persistent-l1", 1), "v037"),
    (V037PackDefinition("matched_nonpersistent_noisy", False, False, "persistent-l2", 2), "v037"),
    (V037PackDefinition("matched_nonpersistent_delayed", False, False, "persistent-l3", 3), "v037"),
    (V037PackDefinition("matched_nonpersistent_compositional", False, False, "persistent-l4", 4), "v037"),
    (V037PackDefinition("observation_routing_composition", True, True, "observation-routing"), "v037"),
    (V037PackDefinition("random_routing_surface", False, False, "routing-surface"), "v037"),
    (V037PackDefinition("grammar_composed_a", True, True, "grammar-a"), "grammar"),
    (V037PackDefinition("grammar_matched_null_a", False, False, "grammar-a"), "grammar"),
    (V037PackDefinition("grammar_composed_b", True, True, "grammar-b"), "grammar"),
    (V037PackDefinition("grammar_matched_null_b", False, False, "grammar-b"), "grammar"),
)

GRAMMAR_FAMILY_TOKENS = (
    "grammar_composed",
    "grammar_matched_null",
)


@dataclass(frozen=True)
class GrammarSpec:
    motifs: tuple[tuple[str, Mapping[str, float]], ...]
    base_signal_weight: float
    decoy_weight: float

    def describe(self) -> str:
        return "+".join(name for name, _ in self.motifs)


def sample_grammar_spec(rng: random.Random) -> GrammarSpec:
    names = rng.sample(GRAMMAR_MOTIFS, rng.choice((2, 3)))
    motifs: list[tuple[str, Mapping[str, float]]] = []
    for name in names:
        if name == "entity_effect":
            params = {"strength": rng.uniform(1.2, 1.9), "corruption": rng.uniform(0.0, 0.25)}
        elif name == "delayed_history":
            params = {"strength": rng.uniform(1.2, 1.8), "window": float(rng.choice((3, 5, 8)))}
        elif name == "regime_flip":
            params = {
                "strength": rng.uniform(1.1, 1.7),
                "threshold": rng.uniform(0.4, 0.7),
                "flip_scale": rng.uniform(-0.9, -0.5),
            }
        elif name == "cross_key_link":
            params = {"strength": rng.uniform(1.0, 1.6)}
        elif name == "path_decay":
            params = {"strength": rng.uniform(1.0, 1.6), "decay": rng.uniform(0.5, 0.9)}
        else:  # routed_signal
            params = {"strength": rng.uniform(1.2, 1.8)}
        motifs.append((name, params))
    return GrammarSpec(
        motifs=tuple(motifs),
        base_signal_weight=rng.uniform(0.3, 0.5),
        decoy_weight=rng.uniform(0.1, 0.3),
    )


def generate_grammar_context(
    spec: GrammarSpec,
    *,
    structure_on: bool,
    seed: int,
    count: int,
) -> list[dict[str, Any]]:
    """Rows in the exact v0.3.x schema; the negative arm zeroes the structure only."""

    generator = random.Random(seed)
    unit_count = 48
    unit_effect = {unit: generator.gauss(0, 1.0) for unit in range(unit_count)}
    secondary_effect = {key: generator.gauss(0, 1.0) for key in range(53)}
    source_history: dict[int, list[float]] = {unit: [] for unit in range(unit_count)}
    decayed: dict[int, float] = dict.fromkeys(range(unit_count), 0.0)
    corruption = 0.0
    for name, params in spec.motifs:
        if name == "entity_effect":
            corruption = params["corruption"]
    rows: list[dict[str, Any]] = []
    for row_id in range(count):
        time = row_id / max(count - 1, 1)
        unit = (row_id * 17 + generator.randrange(13)) % unit_count
        signal = generator.gauss(0, 1)
        source = generator.gauss(0, 1)
        route = generator.randrange(2)
        pattern = (row_id + generator.randrange(4)) % 3
        measure_a = None if pattern == 1 else generator.gauss(0, 1)
        measure_b = None if pattern == 2 else generator.gauss(0, 1)
        heldout = unit_effect[unit] + generator.gauss(0, 0.32)
        frequency_decoy = math.log1p(unit % 8)
        repeated_key: int | None = unit
        secondary_key = (unit * 7 + 3) % 53
        if corruption and generator.random() < corruption:
            repeated_key = None if generator.random() < 0.5 else generator.randrange(unit_count)
        structure = 0.0
        for name, params in spec.motifs:
            if name == "entity_effect":
                structure += params["strength"] * unit_effect[unit]
            elif name == "delayed_history":
                past = source_history[unit][-int(params["window"]) :]
                structure += params["strength"] * (sum(past) / len(past) if past else 0.0)
            elif name == "regime_flip":
                scale = 1.0 if time < params["threshold"] else params["flip_scale"]
                structure += params["strength"] * unit_effect[unit] * scale
            elif name == "cross_key_link":
                structure += params["strength"] * secondary_effect[secondary_key]
            elif name == "path_decay":
                structure += params["strength"] * decayed[unit]
            else:  # routed_signal
                structure += (
                    params["strength"] * 0.6 * ({0: 1.5, 1: -1.4, 2: 0.5}[pattern] + (0.4 if route else -0.35)) * signal
                )
        base = spec.base_signal_weight * signal + spec.decoy_weight * frequency_decoy + 0.15 * time
        if not structure_on:
            base = 0.95 * signal + spec.decoy_weight * frequency_decoy + 0.15 * time
            structure = 0.0
        logit = base + structure
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
                "target": int(generator.random() < _sigmoid(logit)),
                "_oracle": _sigmoid(logit),
                "_control": _sigmoid(base),
                "_independent": structure,
            }
        )
        source_history[unit].append(source)
        decayed[unit] = decayed[unit] * next(
            (params["decay"] for name, params in spec.motifs if name == "path_decay"), 0.0
        ) + signal * (1.0 if any(name == "path_decay" for name, _ in spec.motifs) else 0.0)
    return rows


def _grammar_pair_identifiable(rows_by_context: Sequence[Sequence[Mapping[str, Any]]]) -> bool:
    gains: dict[str, list[float]] = {"research": [], "confirmation": [], "transfer": []}
    for rows in rows_by_context:
        research_end = int(len(rows) * 0.60)
        confirmation_end = int(len(rows) * 0.80)
        spans = {
            "research": rows[:research_end],
            "confirmation": rows[research_end:confirmation_end],
            "transfer": rows[confirmation_end:],
        }
        for name, span in spans.items():
            targets = [int(row["target"]) for row in span]
            oracle = [float(row["_oracle"]) for row in span]
            control = [float(row["_control"]) for row in span]
            gains[name].append(_auc(targets, oracle) - _auc(targets, control))
    med = {name: sorted(values)[len(values) // 2] for name, values in gains.items()}
    return bool(med["research"] > 0.02 and med["confirmation"] > 0 and med["transfer"] > 0)


def accept_grammar_spec(
    *,
    master_seed: int,
    suite_id: str,
    pair: str,
    contexts_per_pack: int,
    rows_per_context: int,
    max_attempts: int = 20,
) -> GrammarSpec:
    """Sample specs until the positive arm is identifiable; deterministic in the seed."""

    for attempt in range(1, max_attempts + 1):
        rng = random.Random(_derive_int(master_seed, suite_id, "grammar-spec", pair, str(attempt)))
        spec = sample_grammar_spec(rng)
        contexts = [
            generate_grammar_context(
                spec,
                structure_on=True,
                seed=_derive_int(master_seed, suite_id, pair, f"context-{index:02d}"),
                count=rows_per_context,
            )
            for index in range(1, contexts_per_pack + 1)
        ]
        if _grammar_pair_identifiable(contexts):
            return spec
    raise RuntimeError(f"no identifiable grammar spec for {suite_id}/{pair} in {max_attempts} attempts")


def build_v040_suite(
    *,
    suite_id: str,
    output_root: Path,
    truth_root: Path,
    key: bytes,
    prompt_paths: Mapping[str, Path],
    policy_contract: Mapping[str, Any],
    contexts_per_pack: int = 3,
    rows_per_context: int = 900,
    suite_ids: Sequence[str] = V040_GEN1_SUITE_IDS,
    master_seed: int = V040_GEN1_MASTER_SEED,
    configs: Mapping[str, Mapping[str, str]] = V040_GEN1_CONFIGS,
    run_ids: Sequence[str] = V040_RUN_IDS,
    max_cycles_per_pack: int = 4,
) -> V037SuiteBuildResult:
    """Build one immutable, blind v0.4.0 suite instance.

    ``suite_ids``/``master_seed``/``configs``/``run_ids`` default to the generation-1 Track A
    design; a study reusing the same grammar/pack-plan machinery (e.g. the codex sol
    reasoning-effort ablation) passes its own preregistered values for these instead of
    duplicating this function.
    """
    if suite_id not in suite_ids:
        raise ValueError("v0.4.0 requires a preregistered suite identity for this study")
    suite_index = suite_ids.index(suite_id) + 1
    if contexts_per_pack < 3 or rows_per_context < 600:
        raise ValueError("aggregate promotion requires three contexts and at least 600 rows")
    if not 1 <= max_cycles_per_pack <= MAX_CYCLES_PER_PACK:
        raise ValueError(f"max_cycles_per_pack must be in [1,{MAX_CYCLES_PER_PACK}] to match the agent contract")
    if output_root.exists() or (truth_root / f"{suite_id}.manifest.enc").exists():
        raise FileExistsError("v0.4.0 suites are immutable; use a new suite identity")
    Fernet(key)
    required_arms = {config["prompt_arm"] for config in configs.values()}
    if not required_arms <= set(prompt_paths):
        raise ValueError(f"prompt_paths is missing frozen prompts for arm(s): {required_arms - set(prompt_paths)}")
    prompt_hashes = {name: _sha256_file(path) for name, path in sorted(prompt_paths.items())}
    policy_hash = hashlib.sha256(json.dumps(policy_contract, sort_keys=True).encode()).hexdigest()
    if not policy_contract.get("null_policy", {}).get("provenance_required"):
        raise ValueError("v0.4.0 requires per-replicate null provenance in the locked policy contract")

    grammar_specs = {
        pair: accept_grammar_spec(
            master_seed=master_seed,
            suite_id=suite_id,
            pair=pair,
            contexts_per_pack=contexts_per_pack,
            rows_per_context=rows_per_context,
        )
        for pair in ("grammar-a", "grammar-b")
    }

    canonical: dict[str, list[tuple[str, list[dict[str, Any]], V037ContextTruth]]] = {}
    for pack_index, (definition, generator_kind) in enumerate(V040_PACK_PLAN, start=1):
        pack_id = f"pack-{pack_index:02d}"
        contexts: list[tuple[str, list[dict[str, Any]], V037ContextTruth]] = []
        for context_index in range(1, contexts_per_pack + 1):
            context_id = f"context-{context_index:02d}"
            if generator_kind == "grammar":
                seed = _derive_int(master_seed, suite_id, definition.matched_pair, context_id)
                rows = generate_grammar_context(
                    grammar_specs[definition.matched_pair],
                    structure_on=definition.structure_present,
                    seed=seed,
                    count=rows_per_context,
                )
            else:
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
                    V037ContextTruth(
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
                        independent_identifiability=0.24 if definition.structure_present else 0.0,
                    ),
                )
            )
        canonical[pack_id] = contexts

    output_root.mkdir(parents=True)
    truth_root.mkdir(parents=True, exist_ok=True)
    aliases: list[V037AliasTruth] = []
    public_hashes: list[str] = []
    for run_id in run_ids:
        agent_id, sampling_seed = _parse_run_id(run_id)
        config = configs[run_id]
        prompt_arm = config["prompt_arm"]
        run_root = output_root / "agent_views" / run_id
        run_root.mkdir(parents=True)
        (run_root / "agent_prompt.md").write_bytes(prompt_paths[prompt_arm].read_bytes())
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
            "version": "0.4.0",
            "suite_id": suite_id,
            "run_id": run_id,
            "agent_id": agent_id,
            "sampling_seed": sampling_seed,
            "prompt_arm": prompt_arm,
            "lineage_policy": V040_LINEAGE_POLICY,
            "prompt_hash": prompt_hashes[prompt_arm],
            "policy_contract_hash": policy_hash,
            "cross_run_information": "none",
            "fresh_context_required": True,
            "max_cycles_per_pack": max_cycles_per_pack,
            "null_policy": policy_contract["null_policy"],
            "confidence_fields": policy_contract["confidence_fields"],
            "null_provenance_fields": policy_contract["null_policy"].get("provenance_fields", []),
            "implication_provenance_required": True,
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
    from dataclasses import asdict

    encrypted_path = truth_root / f"{suite_id}.manifest.enc"
    encrypted_path.write_bytes(Fernet(key).encrypt(json.dumps(asdict(suite_truth), sort_keys=True).encode()))
    encrypted_path.chmod(0o600)
    preflight = preflight_v037_suite(suite_truth)
    return V037SuiteBuildResult(
        suite_id=suite_id,
        run_roots={run_id: str(output_root / "agent_views" / run_id) for run_id in run_ids},
        encrypted_truth_path=str(encrypted_path),
        encrypted_truth_sha256=_sha256_file(encrypted_path),
        public_manifest_sha256=hashlib.sha256("".join(sorted(public_hashes)).encode()).hexdigest(),
        prompt_hashes=prompt_hashes,
        preflight=preflight,
        preflight_passed=all(item.identifiable for item in preflight),
    )
