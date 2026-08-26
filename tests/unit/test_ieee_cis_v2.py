from __future__ import annotations

from epistemic_loop.plugins.ieee_cis import (
    IEEERunAcceptance,
    UIDCandidate,
    UIDValidation,
    client_slice_auc,
    client_slices,
    fold_safe_uid_aggregates,
    generate_uid_candidates,
    ieee_cis_capabilities,
    multi_horizon_forward_folds,
    require_adversarial_followup,
    rolling_window_forward_folds,
)


def test_ieee_plugin_has_dynamic_uids_three_horizons_and_two_model_families() -> None:
    candidates = generate_uid_candidates(
        ["card1", "card2", "addr1", "P_emaildomain", "DeviceInfo", "D1", "TransactionDT"]
    )
    assert any(len(item.columns) >= 3 for item in candidates)
    folds = multi_horizon_forward_folds(
        [str(index) for index in range(20)],
        list(range(20)),
        horizons=3,
        gap_rows=1,
    )
    assert len(folds) == 3
    assert all(fold.purged_row_ids for fold in folds)
    assert len(ieee_cis_capabilities()["model_families"]) >= 2
    rolling = rolling_window_forward_folds(
        [str(index) for index in range(20)],
        list(range(20)),
        horizons=3,
        gap_rows=1,
        train_window_rows=4,
    )
    assert all(len(fold.train_row_ids) <= 4 for fold in rolling)


def test_fold_safe_uid_aggregates_fit_only_training_rows() -> None:
    uid = UIDCandidate("client", ("card1", "addr1"))
    train = [
        {"card1": 1, "addr1": 10, "TransactionAmt": 10.0, "TransactionDT": 1, "D1": 2.0},
        {"card1": 1, "addr1": 10, "TransactionAmt": 30.0, "TransactionDT": 2, "D1": 4.0},
    ]
    validation = [{"card1": 1, "addr1": 10, "TransactionAmt": 9999.0, "TransactionDT": 5, "D1": 999.0}]
    transformed = fold_safe_uid_aggregates(train, validation, uid=uid, aggregate_columns=["D1"])
    assert transformed[0]["uid_amount_mean"] == 20.0
    assert transformed[0]["uid_D1_mean"] == 3.0
    assert transformed[0]["uid_time_delta"] == 3.0


def test_known_new_questionable_client_evaluation() -> None:
    slices = client_slices(["a", "a", "b"], ["a", "c", "b", "c"])
    assert slices == {"known": [0], "new": [1, 3], "questionable": [2]}
    auc = client_slice_auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9], slices)
    assert auc["new_client_auc"] == 1.0


def test_uid_requires_all_seven_promotion_conditions() -> None:
    validation = UIDValidation(True, True, True, True, 3, True, False)
    assert validation.validated is False
    assert UIDValidation(True, True, True, True, 3, True, True).validated is True


def test_adversarial_auc_cannot_directly_change_feature_policy() -> None:
    try:
        require_adversarial_followup(adversarial_auc_changed=True, forward_fraud_validation_completed=False)
    except ValueError as error:
        assert "diagnostic only" in str(error)
    else:  # pragma: no cover
        raise AssertionError("adversarial-only adoption must be rejected")


def test_ieee_run_acceptance_requires_the_complete_candidate_path() -> None:
    acceptance = IEEERunAcceptance(1, 3, 1, True, frozenset({"lightgbm", "logistic"}), 3, 1, 1)
    assert acceptance.passed
    assert IEEERunAcceptance(1, 3, 1, True, frozenset({"lightgbm"}), 3, 1, 1).passed is False
