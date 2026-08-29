from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from epistemic_loop.benchmark.v042_multi_competition_suite import (
    CompetitionSpec,
    _load_frame,
    select_generic_feature_groups,
)


def _write_iid_csv(path: Path, *, rows: int = 40, feature_columns: int = 12) -> None:
    import numpy as np

    rng = np.random.RandomState(0)
    data: dict[str, object] = {"ID_code": [f"row_{i}" for i in range(rows)], "target": rng.randint(0, 2, size=rows)}
    for index in range(feature_columns):
        column = rng.standard_normal(rows)
        # introduce a small amount of missingness on one column to exercise the threshold filter
        if index == feature_columns - 1:
            column[0] = float("nan")
        data[f"var_{index}"] = column
    pd.DataFrame(data).to_csv(path, index=False)


def test_santander_style_spec_has_no_time_column_and_iid_split() -> None:
    spec = CompetitionSpec(
        competition_id="santander-customer-transaction-prediction",
        data_path=Path("unused.csv"),
        target_column="target",
        id_columns=frozenset({"ID_code"}),
        time_column=None,
    )
    assert spec.split_strategy == "iid_random"
    assert spec.excluded_raw_columns == frozenset({"ID_code", "target"})


def test_ieee_cis_style_spec_excludes_time_column_and_uses_temporal_split() -> None:
    spec = CompetitionSpec(
        competition_id="ieee-cis",
        data_path=Path("unused.csv"),
        target_column="isFraud",
        id_columns=frozenset({"TransactionID"}),
        time_column="TransactionDT",
    )
    assert spec.split_strategy == "temporal"
    assert spec.excluded_raw_columns == frozenset({"TransactionID", "isFraud", "TransactionDT"})


def test_select_generic_feature_groups_excludes_id_and_target_and_respects_missingness(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "train.csv"
    _write_iid_csv(csv_path, rows=40, feature_columns=44)
    spec = CompetitionSpec(
        competition_id="synthetic-iid",
        data_path=csv_path,
        target_column="target",
        id_columns=frozenset({"ID_code"}),
        time_column=None,
        missingness_threshold=0.02,
    )
    groups = select_generic_feature_groups(spec, master_seed=1234, suite_id="test-suite-01")
    all_selected = {column for group in groups for column in group}
    assert "ID_code" not in all_selected
    assert "target" not in all_selected
    # var_43 has 1/40 = 2.5% missingness, above the 2% threshold, so it must be excluded
    assert "var_43" not in all_selected


def test_select_generic_feature_groups_folds_suite_id_into_the_seed(tmp_path: Path) -> None:
    csv_path = tmp_path / "train.csv"
    _write_iid_csv(csv_path, rows=40, feature_columns=44)
    spec = CompetitionSpec(
        competition_id="synthetic-iid",
        data_path=csv_path,
        target_column="target",
        id_columns=frozenset({"ID_code"}),
        time_column=None,
    )
    groups_a = select_generic_feature_groups(spec, master_seed=1234, suite_id="suite-a")
    groups_b = select_generic_feature_groups(spec, master_seed=1234, suite_id="suite-b")
    assert groups_a != groups_b


def test_load_frame_iid_random_shuffles_once_deterministically_per_suite(tmp_path: Path) -> None:
    csv_path = tmp_path / "train.csv"
    _write_iid_csv(csv_path, rows=40, feature_columns=12)
    spec = CompetitionSpec(
        competition_id="synthetic-iid",
        data_path=csv_path,
        target_column="target",
        id_columns=frozenset({"ID_code"}),
        time_column=None,
    )
    columns = ["var_0", "var_1", "var_2"]
    frame_a1 = _load_frame(spec, columns, master_seed=1234, suite_id="suite-a")
    frame_a2 = _load_frame(spec, columns, master_seed=1234, suite_id="suite-a")
    frame_b = _load_frame(spec, columns, master_seed=1234, suite_id="suite-b")
    # same suite_id -> identical deterministic row order regardless of which column group is loaded
    assert frame_a1["ID_code"].tolist() == frame_a2["ID_code"].tolist()
    # different suite_id -> a different (still deterministic) shuffle
    assert frame_a1["ID_code"].tolist() != frame_b["ID_code"].tolist()
    # not left in original file order (extremely unlikely by chance with 40 rows)
    assert frame_a1["ID_code"].tolist() != [f"row_{i}" for i in range(40)]


def test_load_frame_requires_target_and_id_columns_present(tmp_path: Path) -> None:
    csv_path = tmp_path / "train.csv"
    _write_iid_csv(csv_path, rows=40, feature_columns=12)
    spec = CompetitionSpec(
        competition_id="synthetic-iid",
        data_path=csv_path,
        target_column="target",
        id_columns=frozenset({"ID_code"}),
        time_column=None,
    )
    frame = _load_frame(spec, ["var_0"], master_seed=1, suite_id="suite-a")
    assert {"ID_code", "target", "var_0", "row_id"} <= set(frame.columns)


def test_load_frame_temporal_sorts_by_time_column(tmp_path: Path) -> None:
    csv_path = tmp_path / "train.csv"
    import numpy as np

    rng = np.random.RandomState(0)
    rows = 30
    frame = pd.DataFrame(
        {
            "TransactionID": range(rows),
            "isFraud": rng.randint(0, 2, size=rows),
            "TransactionDT": rng.permutation(rows),
            "feat_a": rng.standard_normal(rows),
        }
    )
    frame.to_csv(csv_path, index=False)
    spec = CompetitionSpec(
        competition_id="ieee-cis",
        data_path=csv_path,
        target_column="isFraud",
        id_columns=frozenset({"TransactionID"}),
        time_column="TransactionDT",
    )
    loaded = _load_frame(spec, ["feat_a"], master_seed=1, suite_id="suite-a")
    assert loaded["TransactionDT"].is_monotonic_increasing


def test_select_generic_feature_groups_raises_when_pool_too_small(tmp_path: Path) -> None:
    csv_path = tmp_path / "train.csv"
    _write_iid_csv(csv_path, rows=40, feature_columns=5)
    spec = CompetitionSpec(
        competition_id="synthetic-iid",
        data_path=csv_path,
        target_column="target",
        id_columns=frozenset({"ID_code"}),
        time_column=None,
    )
    with pytest.raises(ValueError, match="disjoint column groups"):
        select_generic_feature_groups(spec, master_seed=1, suite_id="suite-a")
