from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from cryptography.fernet import Fernet

from epistemic_loop.benchmark.v037_repro_suite import _auc, _spearman
from epistemic_loop.benchmark.v038_repro_suite import V038_NULL_PROVENANCE_FIELDS
from epistemic_loop.benchmark.v042_multi_competition_suite import (
    CompetitionSpec,
    _fit_capacity_matched_baseline,
    _load_frame,
    build_v042_suite,
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


# --- v0.4.3-c regression support -------------------------------------------------------


def test_competition_spec_defaults_to_classification_metric() -> None:
    spec = CompetitionSpec(
        competition_id="ieee-cis",
        data_path=Path("unused.csv"),
        target_column="isFraud",
        id_columns=frozenset({"TransactionID"}),
        time_column="TransactionDT",
    )
    assert spec.task_type == "classification"
    assert spec.metric is _auc


def test_competition_spec_regression_task_type_selects_spearman_metric() -> None:
    spec = CompetitionSpec(
        competition_id="rossmann-store-sales",
        data_path=Path("unused.csv"),
        target_column="Sales",
        id_columns=frozenset({"Customers"}),
        time_column="Date",
        task_type="regression",
    )
    assert spec.metric is _spearman


def test_competition_spec_rejects_unknown_task_type() -> None:
    with pytest.raises(ValueError, match="task_type"):
        CompetitionSpec(
            competition_id="x",
            data_path=Path("unused.csv"),
            target_column="y",
            id_columns=frozenset(),
            task_type="ranking",
        )


def test_fit_capacity_matched_baseline_regression_branch_learns_linear_signal() -> None:
    rng = np.random.RandomState(0)
    n = 400
    features = pd.DataFrame({"a": rng.standard_normal(n), "b": rng.standard_normal(n)})
    target = pd.Series(3.0 * features["a"] - 2.0 * features["b"] + rng.normal(0, 0.1, size=n))
    model = _fit_capacity_matched_baseline(features, target, task_type="regression")
    predictions = model.predict(features)
    assert _spearman(target.to_numpy(), predictions) > 0.9


def _write_regression_csv(path: Path, *, rows: int, feature_columns: int) -> None:
    # Every column carries a little signal (rather than concentrating it in a few
    # columns) so that any disjoint 10-column group drawn by select_generic_feature_groups
    # clears the identifiability preflight -- this is a mechanism/plumbing test, not a
    # claim about realistic per-column informativeness.
    rng = np.random.RandomState(7)
    data: dict[str, object] = {
        "row_key": range(rows),
        # time_column must be numeric (build_context_rows/_build_row_dicts computes
        # arithmetic min/max/span on it) -- a real "YYYY-MM-DD" Date string would need to
        # be converted to a numeric ordinal first, see
        # docs/verification/v043_rossmann_regression_preregistration.md SS7.
        "Date": range(rows),
    }
    features = rng.standard_normal((rows, feature_columns))
    target = 500.0 + sum(4.0 * features[:, i] for i in range(feature_columns)) + rng.normal(0, 5.0, size=rows)
    for index in range(feature_columns):
        data[f"var_{index}"] = features[:, index]
    data["Sales"] = target
    pd.DataFrame(data).to_csv(path, index=False)


def test_build_v042_suite_regression_end_to_end_synthetic_plumbing(tmp_path: Path) -> None:
    """v0.4.3-c preregistration step 2: synthetic plumbing test for the regression path.

    Uses a synthetic CSV with ample signal-bearing columns (unlike real Rossmann, whose
    raw column count blocks this pipeline -- see
    docs/verification/v043_rossmann_regression_preregistration.md SS7) purely to validate
    that the regression oracle/metric/permutation/packet-building machinery itself works.
    """

    csv_path = tmp_path / "train.csv"
    _write_regression_csv(csv_path, rows=3000, feature_columns=44)
    spec = CompetitionSpec(
        competition_id="synthetic-regression",
        data_path=csv_path,
        target_column="Sales",
        id_columns=frozenset({"row_key"}),
        time_column="Date",
        task_type="regression",
    )
    prompt_paths = {
        "p1": Path("prompts/generic_research_agent/v043_p1_regression.md"),
        "p3": Path("prompts/generic_research_agent/v043_p3_regression.md"),
    }
    policy_contract = {
        "null_policy": {
            "full_refit": True,
            "check_every": 5,
            "minimum": 5,
            "maximum": 30,
            "stops": ["futility", "early_support", "max_replicates"],
            "provenance_required": True,
            "provenance_fields": list(V038_NULL_PROVENANCE_FIELDS),
        },
        "confidence_fields": [
            "p_structure_exists",
            "p_evidence_sufficient",
            "p_actionable",
            "p_positive_transfer",
        ],
        "hidden_regions": ["structure_confirmation", "transfer_sealed"],
        "translations_required": 2,
        "fresh_context_per_run": True,
        "lineage_continuity_enforced": True,
        "terminal_resolution_consistency_enforced": True,
        "implication_provenance_required": True,
    }
    result = build_v042_suite(
        spec,
        output_root=tmp_path / "run",
        truth_root=tmp_path / "truth",
        key=Fernet.generate_key(),
        prompt_paths=prompt_paths,
        policy_contract=policy_contract,
        suite_id="v043-regression-plumbing-test",
        run_ids=("agent-01-s17",),
        configs={"agent-01-s17": {"config_id": "test", "cli": "claude", "model": "test", "prompt_arm": "p1"}},
    )
    assert result.preflight_passed
    assert len(result.preflight) == 8  # 4 candidate + 4 matched-negative twins
    candidates = [item for item in result.preflight if item.structure_present]
    negatives = [item for item in result.preflight if not item.structure_present]
    assert len(candidates) == 4
    assert len(negatives) == 4
    for pack in candidates:
        assert pack.identifiable
        assert pack.research_oracle_gain > 0.1
        assert pack.transfer_oracle_gain > 0.1
    for pack in negatives:
        # _destroy_target_structure should leave the oracle with no real edge over control
        assert abs(pack.transfer_oracle_gain) < 0.1
