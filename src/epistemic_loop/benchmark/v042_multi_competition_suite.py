"""v0.4.2: a competition-agnostic generalization of Track B's real-data blind bridge.

``v041_track_b_suite`` hardcoded IEEE-CIS's file layout (``train_transaction.csv``,
``TransactionID``/``isFraud``/``TransactionDT``). This module factors those choices out
into a :class:`CompetitionSpec` so a new closed Kaggle competition can be added by
declaring its data path, target column, and (if it has one) a time column -- everything
else (pack/context/truth schema, opaque view, encrypted truth, matched-negative
construction via full random permutation of the target within each segment,
identifiability preflight with retry) is unchanged from Track B.

Two split strategies are supported, chosen automatically by whether ``time_column`` is
set:

- ``temporal``: rows are sorted by the time column, then cut 60/20/20 into
  research/confirmation/transfer (IEEE-CIS's original design -- transfer tests
  forward-looking generalization).
- ``iid_random``: no time column exists (e.g. Santander, whose rows are not temporally
  ordered). Rows are deterministically shuffled once per suite, then cut 60/20/20 the
  same way -- transfer here tests iid generalization rather than forward-looking
  generalization, matching the actual structure of that competition's test set.

Regression targets (e.g. Rossmann's continuous ``Sales``) are supported via
``CompetitionSpec.task_type = "regression"`` (v0.4.3-c, see
docs/verification/v043_rossmann_regression_preregistration.md): the oracle becomes a
``HistGradientBoostingRegressor``, the identifiability/gain metric becomes
:func:`_spearman` instead of :func:`_auc`, and ``_destroy_target_structure`` is reused
unchanged (it never assumed a binary target). The agent-facing contract for regression
suites is a *separate* module (``epistemic_loop.controller.v043_regression_agent``) --
the classification contract in ``v037_agent.py`` hard-validates predictions and
self-reported AUC-like statistics into ``[0,1]``, which is wrong for continuous
predictions and a correlation statistic in ``[-1,1]``, and is left untouched.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np
import pandas as pd
from cryptography.fernet import Fernet
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

from epistemic_loop.benchmark.v037_repro_suite import (
    CANONICAL_FEATURES,
    V037AliasTruth,
    V037ContextTruth,
    V037PackDefinition,
    V037SuiteBuildResult,
    V037SuiteTruth,
    _agent_rows,
    _auc,
    _derive_int,
    _opaque_id,
    _sha256_file,
    _spearman,
    _visible_column_map,
    _write_json,
    preflight_v037_suite,
)
from epistemic_loop.controller.v037_agent import MAX_CYCLES_PER_PACK


@dataclass(frozen=True)
class CompetitionSpec:
    """Everything competition-specific that ``build_v042_suite`` needs.

    ``id_columns`` must include every non-feature identifier/leakage column (row ids,
    fold ids, anything derived from the target). ``time_column`` is ``None`` for
    competitions with no meaningful row ordering (selects ``iid_random`` split).
    """

    competition_id: str
    data_path: Path
    target_column: str
    id_columns: frozenset[str]
    time_column: str | None = None
    missingness_threshold: float = 0.02
    task_type: str = "classification"

    def __post_init__(self) -> None:
        if self.task_type not in ("classification", "regression"):
            raise ValueError(f"unknown task_type: {self.task_type!r}")

    @property
    def excluded_raw_columns(self) -> frozenset[str]:
        extra = {self.target_column} | ({self.time_column} if self.time_column else set())
        return self.id_columns | extra

    @property
    def split_strategy(self) -> str:
        return "temporal" if self.time_column else "iid_random"

    @property
    def metric(self) -> Callable[[Sequence[float], Sequence[float]], float]:
        return _spearman if self.task_type == "regression" else _auc


V042_MASTER_SEED = 20261001
V042_MAX_CYCLES_PER_PACK = 4
V042_CONTEXTS_PER_PACK = 3

#: The same 3-execution-config x 4-seed diversity design validated in Track B
#: (docs/c_lite_v041_policy.md SS2.1 / c_lite_v042_policy.md SS2): reused verbatim across
#: every competition -- it is a diversity-lever choice, not a dataset property.
V042_EXECUTION_CONFIGS: Mapping[str, Mapping[str, str]] = {
    **{
        f"agent-01-s{seed}": {"config_id": "MC-opus-P1", "cli": "claude", "model": "claude-opus-5", "prompt_arm": "p1"}
        for seed in (17, 42, 93, 124)
    },
    **{
        f"agent-02-s{seed}": {"config_id": "MC-opus-P3", "cli": "claude", "model": "claude-opus-5", "prompt_arm": "p3"}
        for seed in (17, 42, 93, 124)
    },
    **{
        f"agent-03-s{seed}": {
            "config_id": "MC-sol-P3",
            "cli": "codex",
            "model": "gpt-5.6-sol",
            "prompt_arm": "p3",
            "reasoning_effort": "xhigh",
        }
        for seed in (17, 42, 93, 124)
    },
}
V042_RUN_IDS = tuple(V042_EXECUTION_CONFIGS)

#: Every suite id ever built under this generalized module, across all competitions. New
#: ids are appended here, never reused (matches the project's discard-and-rebuild
#: discipline) and must be kept in sync with scripts/run_v040_agent.py's _CONFIG_REGISTRY
#: before any run through that runner (not required for a build-only preflight check).
#:
#: Suite ids MUST NOT contain a competition-identifying string: ``suite_id`` is written
#: verbatim into the agent-visible packet (``agent_packet.json``'s ``suite_id`` field), so
#: a name like ``v042-mc-santander-01`` would leak the dataset identity straight into the
#: agent's context -- exactly the blindness violation audit_v042_blindness.py exists to
#: catch (and did, on the first Santander build attempt, 2026-08-29). Use opaque letters
#: (a, b, c, ...) for competition order instead.
V042_MC_SUITE_IDS: tuple[str, ...] = (
    "v042-mc-a01",  # IEEE-CIS, build-only regression check for the generalized builder
    "v042-mc-b01",  # Santander, flawed: decile-stratified permutation (see v041-trackb-02)
    "v042-mc-b02",  # Santander, corrected permutation (_destroy_target_structure)
)

_CANDIDATE_PACK_COUNT = 4
_COLUMNS_PER_PACK = len(CANONICAL_FEATURES) - 1  # one slot is the derived relative-time feature
_ROWS_PER_CONTEXT_SEGMENT = {"research": 1080, "confirmation": 360, "transfer": 360}
_INDEPENDENT_IDENTIFIABILITY = {True: 0.24, False: 0.0}


def select_generic_feature_groups(spec: CompetitionSpec, *, master_seed: int, suite_id: str) -> list[list[str]]:
    """Partition the low-missingness numeric column pool into disjoint groups, one per attempt.

    Selection is generic (dtype + missingness threshold, then a seeded shuffle) rather
    than hand-picked, matching Track B's blindness discipline: nothing about which
    columns carry the competition's known predictive structure is used to choose them.
    """

    header = pd.read_csv(spec.data_path, nrows=1)
    numeric_columns = [
        column
        for column, dtype in header.dtypes.items()
        if column not in spec.excluded_raw_columns and pd.api.types.is_numeric_dtype(dtype)
    ]
    missingness = pd.read_csv(spec.data_path, usecols=numeric_columns).isna().mean()
    pool = sorted(column for column in numeric_columns if missingness[column] < spec.missingness_threshold)
    order = list(pool)
    random.Random(_derive_int(master_seed, suite_id, "feature-pool-shuffle")).shuffle(order)
    group_count = len(order) // _COLUMNS_PER_PACK
    if group_count < _CANDIDATE_PACK_COUNT:
        raise ValueError(f"expected at least {_CANDIDATE_PACK_COUNT} disjoint column groups, found {group_count}")
    groups = [order[index * _COLUMNS_PER_PACK : (index + 1) * _COLUMNS_PER_PACK] for index in range(group_count)]
    return groups


def _pack_is_identifiable(
    contexts: Sequence[V037ContextTruth],
    *,
    metric: Callable[[Sequence[float], Sequence[float]], float],
) -> bool:
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
    independent = median(item.independent_identifiability for item in contexts)
    return research > 0.02 and confirmation > 0 and transfer > 0 and independent > 0.05


def _load_frame(spec: CompetitionSpec, columns: Sequence[str], *, master_seed: int, suite_id: str) -> pd.DataFrame:
    usecols = sorted(set(columns) | spec.excluded_raw_columns)
    frame = pd.read_csv(spec.data_path, usecols=usecols)
    if spec.time_column:
        frame = frame.sort_values(spec.time_column, kind="mergesort").reset_index(drop=True)
    else:
        # iid_random: no natural row ordering exists, so fix one deterministically (once
        # per suite, independent of which column group is attempted) before segmenting --
        # otherwise the 60/20/20 cut would be an artifact of file order.
        seed = _derive_int(master_seed, suite_id, "row-order") % (2**32)
        frame = frame.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    frame["row_id"] = frame.index.astype(int)
    return frame


def _segments(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    n = len(frame)
    cut1, cut2 = int(n * 0.60), int(n * 0.80)
    return {
        "research": frame.iloc[:cut1],
        "confirmation": frame.iloc[cut1:cut2],
        "transfer": frame.iloc[cut2:],
    }


def _sample_segment(segment: pd.DataFrame, *, count: int, seed: int) -> pd.DataFrame:
    if count > len(segment):
        raise ValueError(f"requested {count} rows from a segment of {len(segment)}")
    return segment.sample(n=count, random_state=seed).sort_values("row_id").reset_index(drop=True)


def _fit_capacity_matched_baseline(
    features: pd.DataFrame, target: pd.Series, *, task_type: str
) -> HistGradientBoostingClassifier | HistGradientBoostingRegressor:
    # Gradient-boosted trees are the dominant real-world top-solution model class for
    # tabular Kaggle competitions; native NaN handling means no imputer/scaler is needed.
    model_cls = HistGradientBoostingRegressor if task_type == "regression" else HistGradientBoostingClassifier
    model = model_cls(random_state=0)
    model.fit(features, target)
    return model


def _destroy_target_structure(target: np.ndarray, *, seed: int) -> np.ndarray:
    """Full random permutation of the target within a segment.

    Replaces an earlier decile-stratified-by-risk permutation (v041-trackb-01/02, and this
    module's own first Santander build): shuffling labels only *within* each risk-decile
    bucket preserves the *between*-decile positive-rate correlation with risk exactly (bucket
    membership, and therefore each bucket's positive count, is invariant under a within-bucket
    shuffle). Since AUC is a rank statistic, that coarse (10-level) correlation alone is enough
    for any model that can approximately recover decile membership from raw features -- which
    is almost guaranteed, since deciles were defined by a model fit on the same features -- to
    score well above chance. This was empirically confirmed on the IEEE-CIS side: negative-pack
    agent-submitted transfer AUC sat at 0.55-0.73 in both v041-trackb-01 (linear baseline) and
    v041-trackb-02 (HistGradientBoosting baseline), unmoved by the baseline-capacity fix --
    because the flaw was in the permutation's stratification, not the baseline's expressive
    power. A full (unstratified) permutation preserves the segment's marginal positive rate
    exactly (same count of positives, reassigned uniformly at random) while making risk
    statistically independent of target, so AUC(any risk score, permuted target) -> 0.5 in
    expectation. See docs/verification/v041_track_b_qualification.md for the derivation and a
    synthetic reproduction.
    """

    rng = np.random.RandomState(seed)
    return target[rng.permutation(len(target))]


def _coordinate_column(spec: CompetitionSpec) -> str:
    return spec.time_column if spec.time_column else "row_id"


def _build_row_dicts(
    frame: pd.DataFrame,
    feature_columns: Sequence[str],
    *,
    spec: CompetitionSpec,
    segment_bounds: tuple[float, float],
    targets: np.ndarray,
    oracle: np.ndarray,
    control: np.ndarray,
) -> list[dict[str, Any]]:
    segment_min, segment_max = segment_bounds
    span = max(segment_max - segment_min, 1.0)
    coordinate_column = _coordinate_column(spec)
    rows: list[dict[str, Any]] = []
    real_slots = [name for name in CANONICAL_FEATURES if name != "sequence_coordinate"]
    for position, (_, record) in enumerate(frame.iterrows()):
        row: dict[str, Any] = {"row_id": int(record["row_id"])}
        row["sequence_coordinate"] = float((record[coordinate_column] - segment_min) / span)
        for slot, column in zip(real_slots, feature_columns, strict=True):
            value = record[column]
            row[slot] = None if pd.isna(value) else float(value)
        row["target"] = targets[position].item()
        row["_oracle"] = float(oracle[position])
        row["_control"] = float(control[position])
        rows.append(row)
    return rows


def build_context_rows(
    frame: pd.DataFrame,
    segments: Mapping[str, pd.DataFrame],
    feature_columns: Sequence[str],
    *,
    spec: CompetitionSpec,
    pack_index: int,
    context_index: int,
    master_seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (candidate_rows, matched_negative_rows) for one independent context of one pack."""

    sampled: dict[str, pd.DataFrame] = {}
    for name, segment in segments.items():
        seed = _derive_int(master_seed, "sample", str(pack_index), str(context_index), name) % (2**32)
        sampled[name] = _sample_segment(segment, count=_ROWS_PER_CONTEXT_SEGMENT[name], seed=seed)

    target_dtype = float if spec.task_type == "regression" else int
    research_X = sampled["research"][list(feature_columns)]
    research_y = sampled["research"][spec.target_column].to_numpy(dtype=target_dtype)
    baseline = _fit_capacity_matched_baseline(research_X, research_y, task_type=spec.task_type)
    control_rate = float(research_y.mean())

    coordinate_column = _coordinate_column(spec)
    candidate_rows: list[dict[str, Any]] = []
    negative_rows: list[dict[str, Any]] = []
    for name in ("research", "confirmation", "transfer"):
        segment_frame = sampled[name]
        features = segment_frame[list(feature_columns)]
        targets = segment_frame[spec.target_column].to_numpy(dtype=target_dtype)
        oracle = (
            baseline.predict(features) if spec.task_type == "regression" else baseline.predict_proba(features)[:, 1]
        )
        control = np.full(len(segment_frame), control_rate, dtype=float)
        bounds = (float(segment_frame[coordinate_column].min()), float(segment_frame[coordinate_column].max()))
        candidate_rows.extend(
            _build_row_dicts(
                segment_frame,
                feature_columns,
                spec=spec,
                segment_bounds=bounds,
                targets=targets,
                oracle=oracle,
                control=control,
            )
        )
        perm_seed = _derive_int(master_seed, "permute", str(pack_index), str(context_index), name) % (2**32)
        permuted_targets = _destroy_target_structure(targets, seed=perm_seed)
        negative_rows.extend(
            _build_row_dicts(
                segment_frame,
                feature_columns,
                spec=spec,
                segment_bounds=bounds,
                targets=permuted_targets,
                oracle=control,
                control=control,
            )
        )
    return candidate_rows, negative_rows


def _pack_definitions() -> list[tuple[V037PackDefinition, V037PackDefinition]]:
    pairs: list[tuple[V037PackDefinition, V037PackDefinition]] = []
    for index in range(1, _CANDIDATE_PACK_COUNT + 1):
        matched_pair = f"real-pair-{index:02d}"
        candidate = V037PackDefinition(
            family=f"real_candidate_{index:02d}",
            structure_present=True,
            predictive_utility=True,
            matched_pair=matched_pair,
        )
        negative = V037PackDefinition(
            family=f"real_matched_negative_{index:02d}",
            structure_present=False,
            predictive_utility=False,
            matched_pair=matched_pair,
        )
        pairs.append((candidate, negative))
    return pairs


def _context_truth(
    *,
    pack_id: str,
    context_id: str,
    definition: V037PackDefinition,
    generator_seed: int,
    research: Sequence[Mapping[str, Any]],
    confirmation: Sequence[Mapping[str, Any]],
    transfer: Sequence[Mapping[str, Any]],
) -> V037ContextTruth:
    return V037ContextTruth(
        canonical_pack_id=pack_id,
        canonical_context_id=context_id,
        family=definition.family,
        structure_present=definition.structure_present,
        predictive_utility=definition.predictive_utility,
        matched_pair=definition.matched_pair,
        ladder_level=definition.ladder_level,
        generator_seed=generator_seed,
        research_targets=tuple(row["target"] for row in research),
        confirmation_targets=tuple(row["target"] for row in confirmation),
        transfer_targets=tuple(row["target"] for row in transfer),
        oracle_research_predictions=tuple(float(row["_oracle"]) for row in research),
        control_research_predictions=tuple(float(row["_control"]) for row in research),
        oracle_confirmation_predictions=tuple(float(row["_oracle"]) for row in confirmation),
        control_confirmation_predictions=tuple(float(row["_control"]) for row in confirmation),
        oracle_transfer_predictions=tuple(float(row["_oracle"]) for row in transfer),
        control_transfer_predictions=tuple(float(row["_control"]) for row in transfer),
        independent_identifiability=_INDEPENDENT_IDENTIFIABILITY[definition.structure_present],
    )


def build_v042_suite(
    spec: CompetitionSpec,
    *,
    output_root: Path,
    truth_root: Path,
    key: bytes,
    prompt_paths: Mapping[str, Path],
    policy_contract: Mapping[str, Any],
    suite_id: str,
    master_seed: int = V042_MASTER_SEED,
    configs: Mapping[str, Mapping[str, str]] = V042_EXECUTION_CONFIGS,
    run_ids: Sequence[str] = V042_RUN_IDS,
    max_cycles_per_pack: int = V042_MAX_CYCLES_PER_PACK,
    contexts_per_pack: int = V042_CONTEXTS_PER_PACK,
) -> V037SuiteBuildResult:
    if contexts_per_pack < 3:
        raise ValueError("aggregate promotion requires at least three independent contexts per pack")
    if not 1 <= max_cycles_per_pack <= MAX_CYCLES_PER_PACK:
        raise ValueError(f"max_cycles_per_pack must be in [1,{MAX_CYCLES_PER_PACK}] to match the agent contract")
    if output_root.exists() or (truth_root / f"{suite_id}.manifest.enc").exists():
        raise FileExistsError("a v0.4.2 suite is immutable once built; delete both roots to rebuild deliberately")
    Fernet(key)
    required_arms = {config["prompt_arm"] for config in configs.values()}
    if not required_arms <= set(prompt_paths):
        raise ValueError(f"prompt_paths is missing frozen prompts for arm(s): {required_arms - set(prompt_paths)}")
    prompt_hashes = {name: _sha256_file(path) for name, path in sorted(prompt_paths.items())}
    policy_hash = hashlib.sha256(json.dumps(policy_contract, sort_keys=True).encode()).hexdigest()
    if not policy_contract.get("null_policy", {}).get("provenance_required"):
        raise ValueError("v0.4.2 suites require per-replicate null provenance in the locked policy contract")

    feature_groups = select_generic_feature_groups(spec, master_seed=master_seed, suite_id=suite_id)
    pack_defs = _pack_definitions()
    canonical: dict[str, list[tuple[str, list[dict[str, Any]], V037ContextTruth]]] = {}
    attempts: list[dict[str, Any]] = []
    kept = 0
    for attempt_number, columns in enumerate(feature_groups, start=1):
        if kept >= _CANDIDATE_PACK_COUNT:
            break
        candidate_def, negative_def = pack_defs[kept]
        index = kept + 1
        frame = _load_frame(spec, columns, master_seed=master_seed, suite_id=suite_id)
        segments = _segments(frame)
        candidate_pack_id = f"pack-c{index:02d}"
        negative_pack_id = f"pack-n{index:02d}"
        candidate_contexts: list[tuple[str, list[dict[str, Any]], V037ContextTruth]] = []
        negative_contexts: list[tuple[str, list[dict[str, Any]], V037ContextTruth]] = []
        for context_number in range(1, contexts_per_pack + 1):
            context_id = f"context-{context_number:02d}"
            candidate_rows, negative_rows = build_context_rows(
                frame,
                segments,
                columns,
                spec=spec,
                pack_index=index,
                context_index=context_number,
                master_seed=master_seed,
            )
            research_end = _ROWS_PER_CONTEXT_SEGMENT["research"]
            confirmation_end = research_end + _ROWS_PER_CONTEXT_SEGMENT["confirmation"]
            generator_seed = _derive_int(master_seed, candidate_pack_id, context_id)
            for pack_id, definition, rows, bucket in (
                (candidate_pack_id, candidate_def, candidate_rows, candidate_contexts),
                (negative_pack_id, negative_def, negative_rows, negative_contexts),
            ):
                research, confirmation, transfer = (
                    rows[:research_end],
                    rows[research_end:confirmation_end],
                    rows[confirmation_end:],
                )
                truth = _context_truth(
                    pack_id=pack_id,
                    context_id=context_id,
                    definition=definition,
                    generator_seed=generator_seed,
                    research=research,
                    confirmation=confirmation,
                    transfer=transfer,
                )
                bucket.append((context_id, rows, truth))
        identifiable = _pack_is_identifiable([item[2] for item in candidate_contexts], metric=spec.metric)
        attempts.append({"attempt": attempt_number, "columns": list(columns), "identifiable": identifiable})
        if identifiable:
            canonical[candidate_pack_id] = candidate_contexts
            canonical[negative_pack_id] = negative_contexts
            kept += 1
    if kept < _CANDIDATE_PACK_COUNT:
        raise ValueError(
            f"only {kept}/{_CANDIDATE_PACK_COUNT} candidate packs were identifiable after "
            f"{len(feature_groups)} generic column-group attempts; widen the feature pool or "
            "relax the missingness threshold rather than hand-picking columns"
        )

    output_root.mkdir(parents=True)
    truth_root.mkdir(parents=True, exist_ok=True)
    _write_json(
        truth_root / f"{suite_id}.feature_group_attempts.json",
        {"kept": kept, "attempted": len(attempts), "attempts": attempts},
    )
    aliases: list[V037AliasTruth] = []
    public_hashes: list[str] = []
    for run_id in run_ids:
        agent_id, sampling_seed = run_id.rsplit("-s", 1)
        sampling_seed_int = int(sampling_seed)
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
                research_end = _ROWS_PER_CONTEXT_SEGMENT["research"]
                confirmation_end = research_end + _ROWS_PER_CONTEXT_SEGMENT["confirmation"]
                research = _agent_rows(
                    rows[:research_end],
                    column_map,
                    include_target=True,
                    seed=_derive_int(master_seed, run_id, canonical_context_id, canonical_pack_id, "research"),
                )
                confirmation = _agent_rows(
                    rows[research_end:confirmation_end],
                    column_map,
                    include_target=False,
                    seed=_derive_int(master_seed, run_id, canonical_context_id, canonical_pack_id, "confirmation"),
                )
                transfer = _agent_rows(
                    rows[confirmation_end:],
                    column_map,
                    include_target=False,
                    seed=_derive_int(master_seed, run_id, canonical_context_id, canonical_pack_id, "transfer"),
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
                target_by_row = {int(row["row_id"]): row["target"] for row in rows}
                aliases.append(
                    V037AliasTruth(
                        run_id=run_id,
                        agent_id=agent_id,
                        sampling_seed=sampling_seed_int,
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
            "sampling_seed": sampling_seed_int,
            "prompt_arm": prompt_arm,
            "lineage_policy": "posterior_commit",
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
        suite_index=1,
        prompt_hashes=prompt_hashes,
        policy_contract_hash=policy_hash,
        generated_before_agent_runs=True,
        contexts_per_pack=contexts_per_pack,
        context_truth=tuple(item[2] for contexts in canonical.values() for item in contexts),
        aliases=tuple(aliases),
    )
    encrypted_path = truth_root / f"{suite_id}.manifest.enc"
    encrypted_path.write_bytes(Fernet(key).encrypt(json.dumps(asdict(suite_truth), sort_keys=True).encode()))
    encrypted_path.chmod(0o600)
    preflight = preflight_v037_suite(suite_truth, metric=spec.metric)
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
