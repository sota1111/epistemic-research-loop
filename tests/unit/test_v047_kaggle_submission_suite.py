from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from cryptography.fernet import Fernet

from epistemic_loop.benchmark.v042_multi_competition_suite import CompetitionSpec
from epistemic_loop.benchmark.v044_full_feature_pilot import (
    V044_CONFIRMATION_ROWS,
    V044_RESEARCH_ROWS,
    V044_TRANSFER_ROWS,
    _visible_column_map_generic,
)
from epistemic_loop.benchmark.v047_kaggle_submission_suite import (
    V047_CANDIDATE_CONFIGS,
    V047_REAL_TEST_ROW_ID_OFFSET,
    V047_TEST_DATA_PATHS,
    build_v047_suite,
    materialize_real_test_view,
)


def _write_synthetic_csv(path: Path, *, rows: int, feature_columns: int, id_prefix: str) -> None:
    rng = np.random.RandomState(7)
    data: dict[str, object] = {"row_key": [f"{id_prefix}{i}" for i in range(rows)]}
    for index in range(feature_columns):
        data[f"var_{index}"] = rng.standard_normal(rows)
    pd.DataFrame(data).to_csv(path, index=False)


def _spec(train_path: Path) -> CompetitionSpec:
    return CompetitionSpec(
        competition_id="synthetic-pilot",
        data_path=train_path,
        target_column="target",
        id_columns=frozenset({"row_key"}),
        time_column=None,
    )


def test_materialize_real_test_view_salts_columns_and_maps_ids(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    train_path = tmp_path / "train.csv"
    test_path = tmp_path / "test.csv"
    _write_synthetic_csv(train_path, rows=50, feature_columns=6, id_prefix="train_")
    _write_synthetic_csv(test_path, rows=20, feature_columns=6, id_prefix="test_")

    monkeypatch.setitem(V047_TEST_DATA_PATHS, "synthetic-pilot", test_path)

    spec = _spec(train_path)
    columns = [f"var_{i}" for i in range(6)]
    key = Fernet.generate_key()

    view_root = tmp_path / "view"
    id_map_root = tmp_path / "truth"
    result = materialize_real_test_view(
        spec,
        key=key,
        suite_id="suite-x",
        run_id="run-a",
        columns=columns,
        view_root=view_root,
        id_map_root=id_map_root,
    )

    assert result.row_count == 20
    real_test = pd.read_csv(result.real_test_path)
    assert len(real_test) == 20
    assert real_test["row_id"].min() == V047_REAL_TEST_ROW_ID_OFFSET
    assert real_test["row_id"].is_unique

    # feature columns are salted with the SAME function/inputs research/confirmation use,
    # so an agent's existing code (which references those hashed names) applies unchanged
    expected_map = _visible_column_map_generic(key, "suite-x", "run-a", columns)
    assert set(real_test.columns) == {"row_id"} | set(expected_map.values())
    assert "row_key" not in real_test.columns
    assert "var_0" not in real_test.columns

    id_map = json.loads(Path(result.id_map_path).read_text())
    assert id_map["id_column"] == "row_key"
    assert len(id_map["map"]) == 20
    first_row_id = str(int(real_test["row_id"].iloc[0]))
    assert id_map["map"][first_row_id] == "test_0"


def test_materialize_real_test_view_different_run_ids_get_different_salts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    train_path = tmp_path / "train.csv"
    test_path = tmp_path / "test.csv"
    _write_synthetic_csv(train_path, rows=30, feature_columns=4, id_prefix="train_")
    _write_synthetic_csv(test_path, rows=10, feature_columns=4, id_prefix="test_")
    monkeypatch.setitem(V047_TEST_DATA_PATHS, "synthetic-pilot", test_path)

    spec = _spec(train_path)
    columns = [f"var_{i}" for i in range(4)]
    key = Fernet.generate_key()

    result_a = materialize_real_test_view(
        spec,
        key=key,
        suite_id="suite-x",
        run_id="run-a",
        columns=columns,
        view_root=tmp_path / "view-a",
        id_map_root=tmp_path / "truth",
    )
    result_b = materialize_real_test_view(
        spec,
        key=key,
        suite_id="suite-x",
        run_id="run-b",
        columns=columns,
        view_root=tmp_path / "view-b",
        id_map_root=tmp_path / "truth",
    )

    columns_a = set(pd.read_csv(result_a.real_test_path).columns) - {"row_id"}
    columns_b = set(pd.read_csv(result_b.real_test_path).columns) - {"row_id"}
    assert columns_a != columns_b


def _write_train_csv(path: Path, *, rows: int, feature_columns: int, id_prefix: str) -> None:
    rng = np.random.RandomState(11)
    features = rng.standard_normal((rows, feature_columns))
    logit = sum(0.6 * features[:, i] for i in range(min(5, feature_columns))) - 1.0
    probability = 1 / (1 + np.exp(-logit))
    target = (rng.uniform(size=rows) < probability).astype(int)
    data: dict[str, object] = {"row_key": [f"{id_prefix}{i}" for i in range(rows)], "target": target}
    for index in range(feature_columns):
        data[f"var_{index}"] = features[:, index]
    pd.DataFrame(data).to_csv(path, index=False)


def test_build_v047_suite_adds_real_test_to_every_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    train_path = tmp_path / "train.csv"
    test_path = tmp_path / "test.csv"
    total_rows = V044_RESEARCH_ROWS + V044_CONFIRMATION_ROWS + V044_TRANSFER_ROWS
    _write_train_csv(train_path, rows=total_rows + 500, feature_columns=30, id_prefix="train_")
    _write_synthetic_csv(test_path, rows=40, feature_columns=30, id_prefix="test_")
    monkeypatch.setitem(V047_TEST_DATA_PATHS, "synthetic-pilot", test_path)

    spec = _spec(train_path)
    prompt_p1 = tmp_path / "p1.md"
    prompt_p1.write_text("p1 prompt body\n")
    prompt_p3 = tmp_path / "p3.md"
    prompt_p3.write_text("p3 prompt body\n")

    result = build_v047_suite(
        spec,
        output_root=tmp_path / "run" / "suite-01",
        truth_root=tmp_path / "truth",
        real_test_id_map_root=tmp_path / "controller_id_maps",
        key=Fernet.generate_key(),
        scorer_key=Fernet.generate_key(),
        prompt_paths={"p1": prompt_p1, "p3": prompt_p3},
        suite_id="suite-01",
    )

    assert {run.run_id for run in result.suite_build.runs} == set(V047_CANDIDATE_CONFIGS)
    assert len(result.real_test_results) == 12
    for real_test_result in result.real_test_results:
        assert real_test_result.row_count == 40
        real_test = pd.read_csv(real_test_result.real_test_path)
        assert len(real_test) == 40
        assert "row_key" not in real_test.columns
        # research.json (built by build_v044_suite) is untouched by v0.4.7's addition
        view_root = tmp_path / "run" / "suite-01" / "agent_views" / real_test_result.run_id
        assert (view_root / "research.json").exists()
        assert (view_root / "real_test.csv").exists()
