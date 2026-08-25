import pytest

from epistemic_loop.domain.models import OOFRecord
from epistemic_loop.oof.diversity import (
    analyze,
    effective_rank,
    marginal_ensemble_gain,
    pairwise_residual_correlation,
)
from epistemic_loop.oof.store import OOFStore

TARGETS = [0.0, 1.0, 0.0, 1.0]


def _rows(candidate: str, predictions: list[float]) -> list[OOFRecord]:
    return [
        OOFRecord(
            row_id=str(index),
            fold_id=str(index % 2),
            target=target,
            oof_prediction=prediction,
            validation_world="W-time",
            candidate_id=candidate,
        )
        for index, (target, prediction) in enumerate(zip(TARGETS, predictions, strict=True))
    ]


def test_oof_residual_metrics_and_store_round_trip(tmp_path) -> None:
    first = _rows("A", [0.1, 0.8, 0.2, 0.9])
    duplicate = _rows("B", [0.1, 0.8, 0.2, 0.9])
    different = _rows("C", [0.4, 0.9, 0.0, 0.6])
    path = OOFStore().write(tmp_path / "oof.jsonl", [*first, *duplicate, *different])

    restored = OOFStore().read(path)
    report = analyze(restored)

    assert pairwise_residual_correlation(first, duplicate) == pytest.approx(1.0)
    assert report.residual_correlations["A::B"] == pytest.approx(1.0)
    assert 1.0 < report.covariance_effective_rank <= 3.0
    assert len(restored) == 12


def test_effective_rank_and_marginal_gain_have_expected_limits() -> None:
    assert effective_rank([[1, -1, 1, -1], [2, -2, 2, -2]]) == pytest.approx(1.0)
    incumbent = _rows("A", [0.4, 0.6, 0.4, 0.6])
    better = _rows("B", [0.0, 1.0, 0.0, 1.0])
    assert marginal_ensemble_gain([incumbent], better) > 0
