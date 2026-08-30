"""v0.4.4: full-feature-set pilot with an iterative local pseudo-scoring loop.

Every suite through v0.4.3 exposes agents to a fixed 10-column slice of a competition
(``CANONICAL_FEATURES``), inherited unmodified from the synthetic Track A generator's
schema. That constraint is the direct mechanical reason IEEE-CIS's layer-1
(top-solution-technique) match rate has been 0% across every run this session: reaching
a technique like UID reconstruction requires seeing several *specific* columns together,
which a random 10-column draw rarely provides. This module removes that constraint (all
generically-selected low-missingness numeric columns, not a disjoint 10-column group) and
adds a second change: instead of scoring only after every run in a suite is frozen, the
agent can repeatedly submit predictions for a "confirmation" region to a local scoring
tool and see a proxy AUC back -- mirroring Kaggle's public-leaderboard submit/see-score
loop, without an actual Kaggle submission (see
docs/verification/v044_full_feature_pilot_preregistration.md).

This is a *pilot*, not a scaled study: single competition, single run, feasibility check
of the mechanism itself. It intentionally does not reuse v037_agent's cycle/lineage/null-
provenance contract (that machinery targets the formal P2 epistemic-rigor regime; mixing
it with a mechanism feasibility check would conflate two different questions) -- see the
preregistration doc SS4 for the minimal contract used instead.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Sequence
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


@dataclass(frozen=True)
class V044PilotBuildResult:
    suite_id: str
    run_id: str
    view_root: str
    column_count: int
    confirmation_labels_path: str
    transfer_labels_path: str
    reference_baseline_transfer_auc: float


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


def build_v044_pilot(
    spec: CompetitionSpec,
    *,
    output_root: Path,
    truth_root: Path,
    key: bytes,
    scorer_key: bytes,
    prompt_path: Path,
    suite_id: str,
    run_id: str,
    master_seed: int = V044_MASTER_SEED,
) -> V044PilotBuildResult:
    if output_root.exists():
        raise FileExistsError("a v0.4.4 pilot view is immutable once built; delete deliberately to rebuild")
    Fernet(key)
    Fernet(scorer_key)

    columns = select_all_generic_columns(spec)
    if len(columns) < 20:
        raise ValueError(f"expected a rich full-feature column pool, found only {len(columns)}")
    splits = _sample_split(spec, columns, master_seed=master_seed, suite_id=suite_id)
    column_map = _visible_column_map_generic(key, suite_id, run_id, columns)

    research_y = splits["research"][spec.target_column].to_numpy(dtype=int)
    baseline = _fit_capacity_matched_baseline(splits["research"][columns], research_y, task_type="classification")
    transfer_oracle = baseline.predict_proba(splits["transfer"][columns])[:, 1]
    transfer_y = splits["transfer"][spec.target_column].to_numpy(dtype=int)
    reference_baseline_auc = _auc(transfer_y, transfer_oracle)

    view_root = output_root / "agent_views" / run_id
    view_root.mkdir(parents=True)
    research_rows = _rows_to_agent_view(splits["research"], columns, column_map)
    for row, target in zip(research_rows, splits["research"][spec.target_column].tolist(), strict=True):
        row["target"] = int(target)
    confirmation_rows = _rows_to_agent_view(splits["confirmation"], columns, column_map)
    transfer_rows = _rows_to_agent_view(splits["transfer"], columns, column_map)
    _write_json(view_root / "research.json", research_rows)
    _write_json(view_root / "confirmation.json", confirmation_rows)
    _write_json(view_root / "transfer.json", transfer_rows)
    (view_root / "agent_prompt.md").write_bytes(prompt_path.read_bytes())

    packet = {
        "version": "0.4.4",
        "suite_id": suite_id,
        "run_id": run_id,
        "feature_columns": sorted(column_map.values()),
        "target_column": "target",
        "research_file": "research.json",
        "confirmation_file": "confirmation.json",
        "transfer_file": "transfer.json",
        "research_rows": len(research_rows),
        "confirmation_rows": len(confirmation_rows),
        "transfer_rows": len(transfer_rows),
        "confirmation_scorer_command": (
            f"python3 ./score_confirmation.py --suite-id {suite_id} --run-id {run_id} "
            "--predictions <path-to-your-csv, relative to this directory>"
        ),
        "confirmation_scorer_max_calls": V044_MAX_SCORER_CALLS,
        "confirmation_scorer_input_format": "CSV with header row_id,prediction; prediction in [0,1]",
        "prompt_hash": _sha256_file(view_root / "agent_prompt.md"),
    }
    _write_json(view_root / "agent_packet.json", packet)

    truth_root.mkdir(parents=True, exist_ok=True)
    confirmation_labels = _label_map(splits["confirmation"], spec)
    transfer_labels = _label_map(splits["transfer"], spec)
    confirmation_path = truth_root / f"{suite_id}_{run_id}_confirmation_labels.enc"
    transfer_path = truth_root / f"{suite_id}_{run_id}_transfer_labels.enc"
    confirmation_path.write_bytes(Fernet(scorer_key).encrypt(json.dumps(confirmation_labels, sort_keys=True).encode()))
    confirmation_path.chmod(0o600)
    transfer_path.write_bytes(Fernet(key).encrypt(json.dumps(transfer_labels, sort_keys=True).encode()))
    transfer_path.chmod(0o600)

    return V044PilotBuildResult(
        suite_id=suite_id,
        run_id=run_id,
        view_root=str(view_root),
        column_count=len(columns),
        confirmation_labels_path=str(confirmation_path),
        transfer_labels_path=str(transfer_path),
        reference_baseline_transfer_auc=reference_baseline_auc,
    )


def _label_map(frame: pd.DataFrame, spec: CompetitionSpec) -> dict[int, int]:
    return {int(record["row_id"]): int(record[spec.target_column]) for _, record in frame.iterrows()}
