from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from cryptography.fernet import Fernet

from epistemic_loop.benchmark.v037_repro_suite import _auc
from epistemic_loop.benchmark.v042_multi_competition_suite import CompetitionSpec
from epistemic_loop.benchmark.v044_full_feature_pilot import (
    V044_CONFIRMATION_ROWS,
    V044_RESEARCH_ROWS,
    V044_TRANSFER_ROWS,
    _visible_column_map_generic,
    build_v044_pilot,
    select_all_generic_columns,
)


def _write_pilot_csv(path: Path, *, rows: int, feature_columns: int) -> None:
    rng = np.random.RandomState(11)
    features = rng.standard_normal((rows, feature_columns))
    logit = sum(0.6 * features[:, i] for i in range(min(5, feature_columns))) - 1.0
    probability = 1 / (1 + np.exp(-logit))
    target = (rng.uniform(size=rows) < probability).astype(int)
    data: dict[str, object] = {"row_key": range(rows), "target": target}
    for index in range(feature_columns):
        column = features[:, index]
        if index == feature_columns - 1:
            column = column.copy()
            column[:6] = float("nan")  # 6/200 = 3% missingness, above the 0.02 default threshold
        data[f"var_{index}"] = column
    pd.DataFrame(data).to_csv(path, index=False)


def _spec(csv_path: Path) -> CompetitionSpec:
    return CompetitionSpec(
        competition_id="synthetic-pilot",
        data_path=csv_path,
        target_column="target",
        id_columns=frozenset({"row_key"}),
        time_column=None,
    )


def test_select_all_generic_columns_excludes_id_target_and_high_missingness(tmp_path: Path) -> None:
    csv_path = tmp_path / "train.csv"
    _write_pilot_csv(csv_path, rows=200, feature_columns=30)
    spec = _spec(csv_path)
    columns = select_all_generic_columns(spec)
    assert "row_key" not in columns
    assert "target" not in columns
    assert "var_29" not in columns
    assert len(columns) == 29


def test_visible_column_map_generic_is_deterministic_and_unique() -> None:
    key = Fernet.generate_key()
    columns = [f"var_{i}" for i in range(120)]
    map_a = _visible_column_map_generic(key, "suite-1", "run-1", columns)
    map_b = _visible_column_map_generic(key, "suite-1", "run-1", columns)
    map_c = _visible_column_map_generic(key, "suite-1", "run-2", columns)
    assert map_a == map_b
    assert map_a != map_c
    assert len(set(map_a.values())) == len(columns)


def test_build_v044_pilot_end_to_end_synthetic_plumbing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    csv_path = tmp_path / "train.csv"
    total_rows = V044_RESEARCH_ROWS + V044_CONFIRMATION_ROWS + V044_TRANSFER_ROWS
    _write_pilot_csv(csv_path, rows=total_rows + 500, feature_columns=40)
    spec = _spec(csv_path)

    prompt_path = tmp_path / "prompt.md"
    prompt_path.write_text("pilot prompt body\n")

    key = Fernet.generate_key()
    scorer_key = Fernet.generate_key()
    output_root = tmp_path / "run" / "pilot-01"
    truth_root = tmp_path / "truth"
    result = build_v044_pilot(
        spec,
        output_root=output_root,
        truth_root=truth_root,
        key=key,
        scorer_key=scorer_key,
        prompt_path=prompt_path,
        suite_id="pilot-01",
        run_id="agent-01-s1",
    )

    assert result.column_count >= 20
    view_root = output_root / "agent_views" / "agent-01-s1"
    packet = json.loads((view_root / "agent_packet.json").read_text())
    assert packet["research_rows"] == V044_RESEARCH_ROWS
    assert packet["confirmation_rows"] == V044_CONFIRMATION_ROWS
    assert packet["transfer_rows"] == V044_TRANSFER_ROWS
    assert len(packet["feature_columns"]) == result.column_count
    assert "row_key" not in json.dumps(packet)

    research = json.loads((view_root / "research.json").read_text())
    confirmation = json.loads((view_root / "confirmation.json").read_text())
    assert "target" in research[0]
    assert "target" not in confirmation[0]

    confirmation_labels = json.loads(Fernet(scorer_key).decrypt(Path(result.confirmation_labels_path).read_bytes()))
    transfer_labels = json.loads(Fernet(key).decrypt(Path(result.transfer_labels_path).read_bytes()))
    assert len(confirmation_labels) == V044_CONFIRMATION_ROWS
    assert len(transfer_labels) == V044_TRANSFER_ROWS
    assert set(int(v) for v in confirmation_labels.values()) <= {0, 1}

    # the reference baseline should recover real synthetic signal well above chance
    assert result.reference_baseline_transfer_auc > 0.6

    # a perfect-oracle submission scored against the confirmation labels should be ~1.0
    predictions = {row_id: float(label) for row_id, label in confirmation_labels.items()}
    ordered = sorted(confirmation_labels, key=int)
    oracle_auc = _auc(
        [float(confirmation_labels[i]) for i in ordered],
        [predictions[i] for i in ordered],
    )
    assert oracle_auc == pytest.approx(1.0)
