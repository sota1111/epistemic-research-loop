import pytest

from epistemic_loop.domain.models import OOFRecord
from epistemic_loop.oof.ensemble import blend_predictions, build_cross_fitted_ensemble


def _records() -> list[OOFRecord]:
    result = []
    for index, target in enumerate([0.0, 1.0, 0.0, 1.0, 0.0, 1.0]):
        fold = str(index % 3)
        for candidate_id, offset in (("A", 0.1), ("B", -0.1)):
            result.append(
                OOFRecord(
                    row_id=str(index),
                    fold_id=fold,
                    target=target,
                    oof_prediction=target + offset,
                    validation_world="W-time",
                    candidate_id=candidate_id,
                )
            )
    return result


def test_cross_fitted_ensemble_learns_off_fold_weights_and_positive_gain() -> None:
    ensemble = build_cross_fitted_ensemble(_records(), run_id="run", ensemble_id="ENS-1")

    assert ensemble.cross_fitted_loss < ensemble.best_single_loss
    assert ensemble.marginal_gain > 0
    assert set(ensemble.fold_weights) == {"0", "1", "2"}
    assert all(sum(weights.values()) == pytest.approx(1.0) for weights in ensemble.fold_weights.values())
    assert blend_predictions({"A": [0.2, 0.8], "B": [0.4, 0.6]}, {"A": 0.25, "B": 0.75}) == pytest.approx([0.35, 0.65])


def test_held_out_fold_cannot_influence_its_own_weight_search() -> None:
    original = _records()
    modified = [
        item.model_copy(update={"oof_prediction": item.oof_prediction + 50, "residual": None})
        if item.fold_id == "0" and item.candidate_id == "A"
        else item
        for item in original
    ]

    baseline = build_cross_fitted_ensemble(original, run_id="run", ensemble_id="ENS-1")
    attacked = build_cross_fitted_ensemble(modified, run_id="run", ensemble_id="ENS-2")

    assert attacked.fold_weights["0"] == baseline.fold_weights["0"]


def test_ensemble_requires_aligned_rows_and_multiple_folds() -> None:
    one_fold = [item.model_copy(update={"fold_id": "only"}) for item in _records()]
    with pytest.raises(ValueError, match="at least two folds"):
        build_cross_fitted_ensemble(one_fold, run_id="run", ensemble_id="ENS")
