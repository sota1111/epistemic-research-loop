"""v0.4.4: full-feature-set suites with an iterative local pseudo-scoring loop.

Every suite through v0.4.3 exposed agents to a fixed 10-column slice of a competition
(``CANONICAL_FEATURES``), inherited unmodified from the synthetic Track A generator's
schema -- carried into real-data suites (v0.4.1 onward) purely for code-reuse
convenience, and never surfaced to the user as a decision with real tradeoffs (see
docs/verification/v044_ten_column_constraint_incident.md). This module removes that
constraint (all generically-selected low-missingness numeric columns, not a disjoint
10-column group) and adds a second change: instead of scoring only after every run in a
suite is frozen, an agent can repeatedly submit predictions for a "confirmation" region to
a local scoring tool and see a proxy AUC back -- mirroring Kaggle's public-leaderboard
submit/see-score loop, without an actual Kaggle submission (see
docs/verification/v044_full_feature_pilot_preregistration.md and c_lite_v044_policy.md).

``build_v044_suite`` builds a full multi-run suite (mirroring
v042_multi_competition_suite.build_v042_suite's shape): the row split (research/
confirmation/transfer) and confirmation/transfer labels are computed once per suite and
shared across every run_id (the same underlying real rows for every config, exactly like
v042's suites), while each run_id gets its own independently HMAC-salted column-name
hashing and its own agent view directory -- so no run can infer anything about another
run's identity or submissions from the shared label files.

This module intentionally does not reuse v037_agent's cycle/lineage/null-provenance
contract (that machinery targets the formal P2 epistemic-rigor regime; mixing it with this
mechanism would conflate two different questions) -- see the preregistration doc SS4 for
the minimal contract used instead.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from cryptography.fernet import Fernet

from epistemic_loop.benchmark.v037_repro_suite import _auc, _derive_int, _sha256_file, _write_json
from epistemic_loop.benchmark.v042_multi_competition_suite import CompetitionSpec, _fit_capacity_matched_baseline

V044_MASTER_SEED = 20260830044
V044_RESEARCH_ROWS = 5000
V044_CONFIRMATION_ROWS = 1500
V044_TRANSFER_ROWS = 1500
V044_MAX_SCORER_CALLS = 20

#: Same 4-effort x 2-arm design validated in v0.4.3-f (docs/c_lite_v043_policy.md SS10),
#: reused here for the full-feature redo (docs/c_lite_v044_policy.md). Sol/codex only --
#: Claude/opus quota was exhausted this session. Seeds are informational only here (no
#: per-context row sampling in this module -- the whole suite shares one row split), kept
#: for run_id-naming consistency with every other suite in this project.
V044_SOL_EFFORT_CONFIGS: Mapping[str, Mapping[str, str]] = {
    **{
        f"agent-01-s{seed}": {
            "config_id": f"F4-{effort}-P1",
            "cli": "codex",
            "model": "gpt-5.6-sol",
            "prompt_arm": "p1",
            "reasoning_effort": effort,
        }
        for seed, effort in zip((17, 42, 93, 124), ("low", "medium", "high", "xhigh"), strict=True)
    },
    **{
        f"agent-02-s{seed}": {
            "config_id": f"F4-{effort}-P3",
            "cli": "codex",
            "model": "gpt-5.6-sol",
            "prompt_arm": "p3",
            "reasoning_effort": effort,
        }
        for seed, effort in zip((17, 42, 93, 124), ("low", "medium", "high", "xhigh"), strict=True)
    },
}
V044_SOL_EFFORT_RUN_IDS = tuple(V044_SOL_EFFORT_CONFIGS)

#: Round 2 (confirmatory): the screening round succeeded in all 8/8 cells for both
#: competitions (unlike v0.4.3-f's mixed results under the 10-column constraint), so this
#: confirms (a) the single strongest cell (F4-xhigh-P1, best in both competitions) and
#: (b) a P3 cell to test reproducibility of the adversarial-validation finding (present in
#: all 4/4 P3 runs in both competitions) -- same two cells for both competitions, unlike
#: v0.4.3-f's per-competition R2 sets, since the screening pattern was symmetric here. New
#: seeds (271/314/358) do not overlap the screening round's (17/42/93/124).
V044_R2_SEEDS = (271, 314, 358)
V044_R2_CONFIGS: Mapping[str, Mapping[str, str]] = {
    **{
        f"agent-01-s{seed}": {
            "config_id": "F4-xhigh-P1",
            "cli": "codex",
            "model": "gpt-5.6-sol",
            "prompt_arm": "p1",
            "reasoning_effort": "xhigh",
        }
        for seed in V044_R2_SEEDS
    },
    **{
        f"agent-02-s{seed}": {
            "config_id": "F4-xhigh-P3",
            "cli": "codex",
            "model": "gpt-5.6-sol",
            "prompt_arm": "p3",
            "reasoning_effort": "xhigh",
        }
        for seed in V044_R2_SEEDS
    },
}
V044_R2_RUN_IDS = tuple(V044_R2_CONFIGS)

#: Round 3 (population scale-up): round 2 confirmed the P3-arm/adversarial-validation
#: pattern is deterministic (7/7 vs 0/7 per competition), and screening/round 2 both found
#: that Santander's actual dominant public techniques (frequency/count encoding,
#: real-vs-synthetic row detection) never appeared even with all 200 columns visible.
#: v0.4.3-f found that population scale-up (not effort/arm tuning) is what surfaces new
#: technique classes once a config is confirmed robust -- this round tests whether that
#: holds here too: does a larger F4-xhigh-P3 population (now n=11 combined) finally
#: surface Santander's missing techniques, or new diversity for IEEE-CIS? New seeds
#: (512/634/777/901) do not overlap rounds 1-2.
V044_R3_SEEDS = (512, 634, 777, 901)
V044_R3_CONFIGS: Mapping[str, Mapping[str, str]] = {
    f"agent-01-s{seed}": {
        "config_id": "F4-xhigh-P3",
        "cli": "codex",
        "model": "gpt-5.6-sol",
        "prompt_arm": "p3",
        "reasoning_effort": "xhigh",
    }
    for seed in V044_R3_SEEDS
}
V044_R3_RUN_IDS = tuple(V044_R3_CONFIGS)

#: v0.4.5 cells C/D (docs/c_lite_v045_policy.md SS2): 10-column limit (the v0.4.3-f
#: constraint, reintroduced deliberately via column_limit) WITH the iterative confirmation-
#: scoring loop, at xhigh effort, both prompt arms -- isolates the feedback-loop factor from
#: the column-count factor. New seeds, no overlap with rounds 1-3.
V044_R4_SEEDS = (1033, 1147, 1258, 1369)
V044_R4_CONFIGS: Mapping[str, Mapping[str, str]] = {
    **{
        f"agent-01-s{seed}": {
            "config_id": "F5-10col-fb-P1",
            "cli": "codex",
            "model": "gpt-5.6-sol",
            "prompt_arm": "p1",
            "reasoning_effort": "xhigh",
        }
        for seed in V044_R4_SEEDS
    },
    **{
        f"agent-02-s{seed}": {
            "config_id": "F5-10col-fb-P3",
            "cli": "codex",
            "model": "gpt-5.6-sol",
            "prompt_arm": "p3",
            "reasoning_effort": "xhigh",
        }
        for seed in V044_R4_SEEDS
    },
}
V044_R4_RUN_IDS = tuple(V044_R4_CONFIGS)

#: v0.4.5 cells E/F (docs/c_lite_v045_policy.md SS2): full column pool WITHOUT the
#: confirmation-scoring loop (one-shot, exactly like v0.4.3-f's scoring regime), at xhigh
#: effort, both prompt arms -- isolates the column-count factor from the feedback-loop
#: factor. New seeds, no overlap with rounds 1-4.
V044_R5_SEEDS = (1481, 1592, 1703, 1814)
V044_R5_CONFIGS: Mapping[str, Mapping[str, str]] = {
    **{
        f"agent-01-s{seed}": {
            "config_id": "F5-full-nofb-P1",
            "cli": "codex",
            "model": "gpt-5.6-sol",
            "prompt_arm": "p1",
            "reasoning_effort": "xhigh",
        }
        for seed in V044_R5_SEEDS
    },
    **{
        f"agent-02-s{seed}": {
            "config_id": "F5-full-nofb-P3",
            "cli": "codex",
            "model": "gpt-5.6-sol",
            "prompt_arm": "p3",
            "reasoning_effort": "xhigh",
        }
        for seed in V044_R5_SEEDS
    },
}
V044_R5_RUN_IDS = tuple(V044_R5_CONFIGS)

#: v0.4.6 cells I/J (docs/c_lite_v046_policy.md SS3): full columns, NO confirmation-
#: scoring loop, at LOW effort (the opposite end of v0.4.5's xhigh-fixed design), both
#: prompt arms. Sol is the primary arm (n=4/comp, toward this project's standard
#: reproducibility bar); a small opus/claude screening arm (n=1/comp, agent-03/agent-04
#: run_ids) is layered in per the user's explicit request to include a few opus runs even
#: though this harness has no reasoning-effort dial for claude. New seeds, no overlap with
#: any prior round.
V046_LOW_NOFB_SOL_SEEDS = (2001, 2114, 2237, 2358)
V046_LOW_NOFB_OPUS_SEEDS = (3001,)
V046_LOW_NOFB_CONFIGS: Mapping[str, Mapping[str, str]] = {
    **{
        f"agent-01-s{seed}": {
            "config_id": "F6-low-nofb-P1",
            "cli": "codex",
            "model": "gpt-5.6-sol",
            "prompt_arm": "p1",
            "reasoning_effort": "low",
        }
        for seed in V046_LOW_NOFB_SOL_SEEDS
    },
    **{
        f"agent-02-s{seed}": {
            "config_id": "F6-low-nofb-P3",
            "cli": "codex",
            "model": "gpt-5.6-sol",
            "prompt_arm": "p3",
            "reasoning_effort": "low",
        }
        for seed in V046_LOW_NOFB_SOL_SEEDS
    },
    **{
        f"agent-03-s{seed}": {
            "config_id": "F6-opus-nofb-P1",
            "cli": "claude",
            "model": "claude-opus-5",
            "prompt_arm": "p1",
        }
        for seed in V046_LOW_NOFB_OPUS_SEEDS
    },
    **{
        f"agent-04-s{seed}": {
            "config_id": "F6-opus-nofb-P3",
            "cli": "claude",
            "model": "claude-opus-5",
            "prompt_arm": "p3",
        }
        for seed in V046_LOW_NOFB_OPUS_SEEDS
    },
}
V046_LOW_NOFB_RUN_IDS = tuple(V046_LOW_NOFB_CONFIGS)

#: v0.4.6 cells K/L (docs/c_lite_v046_policy.md SS3): full columns, WITH the confirmation-
#: scoring loop, at LOW effort. Sol seeds here are new (do not overlap the existing
#: F4-low-P1/F4-low-P3 screening seed 17 from v044-suite-a01/b01, which this suite's own
#: build does NOT include -- that single existing seed per competition is pooled in at
#: analysis time by reading its diagnostics JSON directly, per c_lite_v046_policy.md SS6,
#: not re-run here). Same small opus screening arm as I/J above.
V046_LOW_FB_SOL_SEEDS = (2481, 2592, 2703)
V046_LOW_FB_OPUS_SEEDS = (3002,)
V046_LOW_FB_CONFIGS: Mapping[str, Mapping[str, str]] = {
    **{
        f"agent-01-s{seed}": {
            "config_id": "F6-low-fb-P1",
            "cli": "codex",
            "model": "gpt-5.6-sol",
            "prompt_arm": "p1",
            "reasoning_effort": "low",
        }
        for seed in V046_LOW_FB_SOL_SEEDS
    },
    **{
        f"agent-02-s{seed}": {
            "config_id": "F6-low-fb-P3",
            "cli": "codex",
            "model": "gpt-5.6-sol",
            "prompt_arm": "p3",
            "reasoning_effort": "low",
        }
        for seed in V046_LOW_FB_SOL_SEEDS
    },
    **{
        f"agent-03-s{seed}": {
            "config_id": "F6-opus-fb-P1",
            "cli": "claude",
            "model": "claude-opus-5",
            "prompt_arm": "p1",
        }
        for seed in V046_LOW_FB_OPUS_SEEDS
    },
    **{
        f"agent-04-s{seed}": {
            "config_id": "F6-opus-fb-P3",
            "cli": "claude",
            "model": "claude-opus-5",
            "prompt_arm": "p3",
        }
        for seed in V046_LOW_FB_OPUS_SEEDS
    },
}
V046_LOW_FB_RUN_IDS = tuple(V046_LOW_FB_CONFIGS)


@dataclass(frozen=True)
class V044RunBuildResult:
    run_id: str
    view_root: str


@dataclass(frozen=True)
class V044SuiteBuildResult:
    suite_id: str
    column_count: int
    reference_baseline_transfer_auc: float
    confirmation_labels_path: str | None
    transfer_labels_path: str
    runs: tuple[V044RunBuildResult, ...]


def select_all_generic_columns(spec: CompetitionSpec) -> list[str]:
    """Every generically-selected (dtype + missingness) numeric column, ungrouped.

    Same filter as ``v042_multi_competition_suite.select_generic_feature_groups``, minus
    the disjoint-10-column grouping -- the whole point of this module is to drop that
    grouping, not reproduce it.
    """

    header = pd.read_csv(spec.data_path, nrows=1)
    numeric_columns = [
        column
        for column, dtype in header.dtypes.items()
        if column not in spec.excluded_raw_columns and pd.api.types.is_numeric_dtype(dtype)
    ]
    missingness = pd.read_csv(spec.data_path, usecols=numeric_columns).isna().mean()
    return sorted(column for column in numeric_columns if missingness[column] < spec.missingness_threshold)


def _select_column_subset(columns: Sequence[str], column_limit: int, *, master_seed: int, suite_id: str) -> list[str]:
    """Deterministically subsample the generic column pool to ``column_limit`` columns.

    Used by the v0.4.5 factorial design (docs/c_lite_v045_policy.md SS3) to reintroduce a
    10-column condition without hand-picking which 10 -- same generic-selection principle
    as select_all_generic_columns, just narrower. Seeded from suite_id + master_seed only
    (never run_id), so every run_id in a suite sees the same column subset, matching how
    the full-column suites already share one row split across run_ids.
    """

    if column_limit > len(columns):
        raise ValueError(f"column_limit={column_limit} exceeds available column pool ({len(columns)})")
    seed = _derive_int(master_seed, suite_id, "column-limit") % (2**32)
    return sorted(random.Random(seed).sample(sorted(columns), column_limit))


def _visible_column_map_generic(key: bytes, suite_id: str, run_id: str, columns: Sequence[str]) -> dict[str, str]:
    width = max(3, len(str(len(columns) - 1)))
    output: dict[str, str] = {}
    for index, canonical in enumerate(sorted(columns)):
        payload = f"{suite_id}:{run_id}:{canonical}".encode()
        digest = hmac.new(key, payload, hashlib.sha256).hexdigest()
        output[canonical] = f"x_{index:0{width}d}_{digest[:7]}"
    return output


def _sample_split(
    spec: CompetitionSpec, columns: Sequence[str], *, master_seed: int, suite_id: str
) -> dict[str, pd.DataFrame]:
    total = V044_RESEARCH_ROWS + V044_CONFIRMATION_ROWS + V044_TRANSFER_ROWS
    usecols = sorted(set(columns) | spec.excluded_raw_columns)
    frame = pd.read_csv(spec.data_path, usecols=usecols)
    if spec.time_column:
        frame = frame.sort_values(spec.time_column, kind="mergesort").reset_index(drop=True)
    else:
        seed = _derive_int(master_seed, suite_id, "row-order") % (2**32)
        frame = frame.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    if len(frame) < total:
        raise ValueError(f"need {total} rows, only {len(frame)} available")
    sample_seed = _derive_int(master_seed, suite_id, "row-sample") % (2**32)
    sampled = frame.sample(n=total, random_state=sample_seed).reset_index(drop=True)
    sampled["row_id"] = sampled.index.astype(int)
    return {
        "research": sampled.iloc[:V044_RESEARCH_ROWS].reset_index(drop=True),
        "confirmation": sampled.iloc[V044_RESEARCH_ROWS : V044_RESEARCH_ROWS + V044_CONFIRMATION_ROWS].reset_index(
            drop=True
        ),
        "transfer": sampled.iloc[V044_RESEARCH_ROWS + V044_CONFIRMATION_ROWS :].reset_index(drop=True),
    }


def _rows_to_agent_view(
    frame: pd.DataFrame, columns: Sequence[str], column_map: dict[str, str]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, record in frame.iterrows():
        row: dict[str, Any] = {"row_id": int(record["row_id"])}
        for column in columns:
            value = record[column]
            row[column_map[column]] = None if pd.isna(value) else float(value)
        rows.append(row)
    return rows


def _label_map(frame: pd.DataFrame, spec: CompetitionSpec) -> dict[int, int]:
    return {int(record["row_id"]): int(record[spec.target_column]) for _, record in frame.iterrows()}


def build_v044_suite(
    spec: CompetitionSpec,
    *,
    output_root: Path,
    truth_root: Path,
    key: bytes,
    scorer_key: bytes,
    prompt_paths: Mapping[str, Path],
    suite_id: str,
    configs: Mapping[str, Mapping[str, str]] = V044_SOL_EFFORT_CONFIGS,
    run_ids: Sequence[str] = V044_SOL_EFFORT_RUN_IDS,
    master_seed: int = V044_MASTER_SEED,
    column_limit: int | None = None,
    enable_confirmation_scoring: bool = True,
) -> V044SuiteBuildResult:
    if output_root.exists():
        raise FileExistsError("a v0.4.4 suite is immutable once built; delete both roots to rebuild deliberately")
    Fernet(key)
    Fernet(scorer_key)
    required_arms = {configs[run_id]["prompt_arm"] for run_id in run_ids}
    if not required_arms <= set(prompt_paths):
        raise ValueError(f"prompt_paths is missing frozen prompts for arm(s): {required_arms - set(prompt_paths)}")

    columns = select_all_generic_columns(spec)
    if len(columns) < 20:
        raise ValueError(f"expected a rich full-feature column pool, found only {len(columns)}")
    if column_limit is not None:
        columns = _select_column_subset(columns, column_limit, master_seed=master_seed, suite_id=suite_id)
    splits = _sample_split(spec, columns, master_seed=master_seed, suite_id=suite_id)

    research_y = splits["research"][spec.target_column].to_numpy(dtype=int)
    baseline = _fit_capacity_matched_baseline(splits["research"][columns], research_y, task_type="classification")
    transfer_oracle = baseline.predict_proba(splits["transfer"][columns])[:, 1]
    transfer_y = splits["transfer"][spec.target_column].to_numpy(dtype=int)
    reference_baseline_auc = _auc(transfer_y, transfer_oracle)

    truth_root.mkdir(parents=True, exist_ok=True)
    transfer_labels = _label_map(splits["transfer"], spec)
    transfer_path = truth_root / f"{suite_id}_transfer_labels.enc"
    transfer_path.write_bytes(Fernet(key).encrypt(json.dumps(transfer_labels, sort_keys=True).encode()))
    transfer_path.chmod(0o600)
    confirmation_path: Path | None = None
    if enable_confirmation_scoring:
        confirmation_labels = _label_map(splits["confirmation"], spec)
        confirmation_path = truth_root / f"{suite_id}_confirmation_labels.enc"
        confirmation_path.write_bytes(
            Fernet(scorer_key).encrypt(json.dumps(confirmation_labels, sort_keys=True).encode())
        )
        confirmation_path.chmod(0o600)

    runs: list[V044RunBuildResult] = []
    for run_id in run_ids:
        prompt_arm = configs[run_id]["prompt_arm"]
        column_map = _visible_column_map_generic(key, suite_id, run_id, columns)
        view_root = output_root / "agent_views" / run_id
        view_root.mkdir(parents=True)
        research_rows = _rows_to_agent_view(splits["research"], columns, column_map)
        for row, target in zip(research_rows, splits["research"][spec.target_column].tolist(), strict=True):
            row["target"] = int(target)
        transfer_rows = _rows_to_agent_view(splits["transfer"], columns, column_map)
        _write_json(view_root / "research.json", research_rows)
        _write_json(view_root / "transfer.json", transfer_rows)
        (view_root / "agent_prompt.md").write_bytes(prompt_paths[prompt_arm].read_bytes())

        packet = {
            "version": "0.4.4",
            "suite_id": suite_id,
            "run_id": run_id,
            "feature_columns": sorted(column_map.values()),
            "target_column": "target",
            "research_file": "research.json",
            "transfer_file": "transfer.json",
            "research_rows": len(research_rows),
            "transfer_rows": len(transfer_rows),
        }
        if enable_confirmation_scoring:
            confirmation_rows = _rows_to_agent_view(splits["confirmation"], columns, column_map)
            _write_json(view_root / "confirmation.json", confirmation_rows)
            packet["confirmation_file"] = "confirmation.json"
            packet["confirmation_rows"] = len(confirmation_rows)
            packet["confirmation_scorer_command"] = (
                f"python3 ./score_confirmation.py --suite-id {suite_id} --run-id {run_id} "
                "--predictions <path-to-your-csv, relative to this directory>"
            )
            packet["confirmation_scorer_max_calls"] = V044_MAX_SCORER_CALLS
            packet["confirmation_scorer_input_format"] = "CSV with header row_id,prediction; prediction in [0,1]"
        packet["prompt_hash"] = _sha256_file(view_root / "agent_prompt.md")
        _write_json(view_root / "agent_packet.json", packet)
        runs.append(V044RunBuildResult(run_id=run_id, view_root=str(view_root)))

    return V044SuiteBuildResult(
        suite_id=suite_id,
        column_count=len(columns),
        reference_baseline_transfer_auc=reference_baseline_auc,
        confirmation_labels_path=str(confirmation_path) if confirmation_path is not None else None,
        transfer_labels_path=str(transfer_path),
        runs=tuple(runs),
    )
