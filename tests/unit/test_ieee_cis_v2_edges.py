from __future__ import annotations

import pytest

from epistemic_loop.plugins.ieee_cis import (
    UIDCandidate,
    binary_auc,
    client_frequency_slices,
    client_level_average,
    client_slice_auc,
    fold_safe_uid_aggregates,
    generate_uid_candidates,
    histogram_calibration,
    known_new_routing,
    make_model_family,
    model_rank_stability,
    multi_horizon_forward_folds,
    rank_blend,
    temporal_smoothing,
    uid_value,
)


def test_uid_generation_values_missing_aggregates_and_frequency_slices() -> None:
    assert generate_uid_candidates(["addr1"]) == ()
    limited = generate_uid_candidates(["card1", "addr1", "D1"], maximum=2)
    assert len(limited) == 2
    uid = UIDCandidate("u", ("card1", "addr1"))
    assert len(uid_value({"card1": 1, "addr1": None}, uid)) == 24
    transformed = fold_safe_uid_aggregates(
        [{"card1": 1, "addr1": 2, "TransactionAmt": None, "TransactionDT": None}],
        [{"card1": 9, "addr1": 9, "TransactionAmt": "nan", "TransactionDT": "bad"}],
        uid=uid,
        aggregate_columns=["D1"],
    )
    assert transformed[0]["uid_count"] == 0
    frequencies = client_frequency_slices(["a"] * 6 + ["b"] * 3 + ["c"], ["x", "c", "b", "a"])
    assert frequencies == {
        "frequency_0": [0],
        "frequency_1": [1],
        "frequency_2_5": [2],
        "frequency_6_plus": [3],
    }


def test_client_post_processing_calibration_and_rank_functions() -> None:
    assert client_level_average([0.1, 0.3, 0.9], ["a", "a", "b"]) == [0.2, 0.2, 0.9]
    assert known_new_routing([0.1, 0.2], [0.8, 0.9], [0]) == [0.8, 0.2]
    smoothed = temporal_smoothing([0.2, 0.8], ["a", "a"], strength=0.5)
    assert smoothed == [0.2, 0.5]
    calibrated = histogram_calibration([0.1, 0.9], [0, 1], [0.1, 0.9], bins=2)
    assert calibrated == [0.0, 1.0]
    blended = rank_blend({"a": [0.1, 0.9], "b": [0.2, 0.8]})
    assert blended == [0.0, 1.0]
    assert model_rank_stability({"a": [0.9, 0.8], "b": [0.8, 0.7]}) == 1.0
    with pytest.raises(ValueError):
        known_new_routing([0.1], [0.1, 0.2], [])
    with pytest.raises(ValueError):
        temporal_smoothing([0.1], ["a"], strength=2)
    with pytest.raises(ValueError):
        histogram_calibration([], [], [], bins=1)
    with pytest.raises(ValueError):
        rank_blend({"a": [0.1]})
    with pytest.raises(ValueError):
        model_rank_stability({"a": [0.1]})


def test_auc_slice_and_forward_errors() -> None:
    assert binary_auc([0, 1, 0, 1], [0.5, 0.5, 0.1, 0.9]) > 0.5
    slices = {"known": [0], "new": [1, 2]}
    values = client_slice_auc([0, 1, 0], [0.1, 0.9, 0.2], slices)
    assert values["known_client_auc"] is None
    with pytest.raises(ValueError):
        binary_auc([1], [0.2])
    with pytest.raises(ValueError):
        client_slice_auc([0], [0.1, 0.2], slices)
    with pytest.raises(ValueError):
        multi_horizon_forward_folds(["1", "2"], [1, 2], horizons=2)
    with pytest.raises(ValueError):
        multi_horizon_forward_folds([str(i) for i in range(8)], list(range(8)), horizons=3, gap_rows=0)
    with pytest.raises(ValueError, match="unsupported"):
        make_model_family("unknown")


def test_optional_model_factory() -> None:
    pytest.importorskip("sklearn.linear_model")
    assert make_model_family("logistic").__class__.__name__ == "LogisticRegression"
