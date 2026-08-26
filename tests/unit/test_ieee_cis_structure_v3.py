from __future__ import annotations

from collections import Counter, defaultdict

from epistemic_loop.domain.enums import StructureClassification
from epistemic_loop.plugins.ieee_cis import (
    IEEERunAcceptance,
    UIDCandidate,
    UIDNestedAblationEvidence,
    evaluate_behavioral_client_proxy,
    evaluate_structure_validator_controls,
    fold_safe_uid_history_features,
    frequency_matched_null_assignments,
    generate_behavioral_client_synthetic_control,
    heldout_feature_consistency,
    synthetic_behavioral_client_evidence,
    uid_competing_hypotheses,
)


def _passing_evidence() -> UIDNestedAblationEvidence:
    positive_blocks = (0.02, 0.025, 0.03, 0.028, 0.024, 0.027)
    return UIDNestedAblationEvidence(
        score_by_model={
            "M0_BASE": 0.90,
            "M1_COMPONENTS": 0.905,
            "M2_FREQUENCY": 0.91,
            "M3_UID_MEMORY": 0.94,
            "M4_LINK_SHUFFLED": 0.915,
            "M5_MATCHED_NULL": 0.912,
        },
        uid_free_gain_blocks=positive_blocks,
        frequency_gain_blocks=(0.004, 0.006, 0.005),
        identity_gain_blocks=positive_blocks,
        linkage_gain_blocks=(0.018, 0.024, 0.021, 0.026),
        matched_null_gains=tuple(0.001 + index * 0.0002 for index in range(20)),
        construct_validity_gains=(0.08, 0.07, 0.09, 0.06),
        temporal_persistence_gains=(0.10, 0.08, 0.09, 0.11),
        horizon_identity_gains=(0.02, 0.03, 0.025),
        seed_identity_gains=(0.021, 0.026, 0.024),
        known_identity_gain=0.04,
        new_identity_gain=0.005,
        matched_null_interactions=tuple(0.001 + index * 0.0001 for index in range(20)),
        fold_safe=True,
        decision_adopted=True,
    )


def test_uid_claim_registers_competing_models_not_just_a_gain_claim() -> None:
    alternatives = uid_competing_hypotheses()
    assert set(alternatives) == {
        "H_client",
        "H_frequency",
        "H_time",
        "H_components",
        "H_linkage_noise",
        "H_leakage",
        "H_sparse_overfit",
    }


def test_frequency_matched_null_preserves_every_stratum_multiset() -> None:
    uids = ["a", "b", "c", "a", "b", "c", "a", "b", "c", "a", "b", "c"]
    time_bins = [0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3]
    missingness = [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1]
    shuffled = frequency_matched_null_assignments(uids, time_bins, missingness, seed=8)
    original_by_stratum: dict[tuple[int, int], Counter[str]] = defaultdict(Counter)
    shuffled_by_stratum: dict[tuple[int, int], Counter[str]] = defaultdict(Counter)
    for uid, shuffled_uid, time_bin, missing in zip(uids, shuffled, time_bins, missingness, strict=True):
        original_by_stratum[(time_bin, missing)][uid] += 1
        shuffled_by_stratum[(time_bin, missing)][str(shuffled_uid)] += 1
    assert original_by_stratum == shuffled_by_stratum
    assert Counter(uids) == Counter(shuffled)


def test_behavioral_client_proxy_requires_all_nine_gates() -> None:
    passed = evaluate_behavioral_client_proxy(_passing_evidence())
    assert passed.passed
    assert all(passed.gates.values())
    assert passed.classification == StructureClassification.VALIDATED_ACTIONABLE_STRUCTURE
    assert passed.acceptance_level == 1.0

    scores = dict(_passing_evidence().score_by_model)
    scores["M4_LINK_SHUFFLED"] = scores["M3_UID_MEMORY"]
    failed_link = UIDNestedAblationEvidence(
        **{
            **_passing_evidence().__dict__,
            "score_by_model": scores,
            "linkage_gain_blocks": (0.0, 0.0, 0.0),
        }
    )
    result = evaluate_behavioral_client_proxy(failed_link)
    assert result.gates["G5_linkage_dependence"] is False
    assert result.classification == StructureClassification.USEFUL_ENCODING_UNVALIDATED_STRUCTURE
    assert result.acceptance_level == 0.75


def test_construct_validity_uses_uid_unused_attributes() -> None:
    real = heldout_feature_consistency(["a", "a", "b", "b"], ["x", "x", "y", "y"])
    null = heldout_feature_consistency(["a", "b", "a", "b"], ["x", "x", "y", "y"])
    assert real == 1.0
    assert null == 0.5


def test_uid_fraud_history_reads_only_fit_rows() -> None:
    uid = UIDCandidate("client", ("card", "addr"))
    fit = [
        {"card": "a", "addr": "x", "TransactionDT": 1, "isFraud": 0},
        {"card": "a", "addr": "x", "TransactionDT": 2, "isFraud": 1},
        {"card": "a", "addr": "x", "TransactionDT": 5, "isFraud": 1},
    ]
    validation = [{"card": "a", "addr": "x", "TransactionDT": 4, "isFraud": 0}]
    changed_label = [{**validation[0], "isFraud": 1}]
    expected = fold_safe_uid_history_features(fit, validation, uid=uid)
    assert fold_safe_uid_history_features(fit, changed_label, uid=uid) == expected
    assert expected == [{"uid_history_count": 2.0, "uid_history_fraud_rate": 0.5, "uid_history_recency": 2.0}]


def test_synthetic_positive_passes_and_frequency_matched_negative_is_rejected() -> None:
    positive = evaluate_behavioral_client_proxy(
        synthetic_behavioral_client_evidence(
            generate_behavioral_client_synthetic_control(persistent_link=True, seed=42),
            seed=42,
        )
    )
    negative = evaluate_behavioral_client_proxy(
        synthetic_behavioral_client_evidence(
            generate_behavioral_client_synthetic_control(persistent_link=False, seed=42),
            seed=42,
        )
    )
    report = evaluate_structure_validator_controls(
        [positive],
        [negative],
        elapsed_minutes=0.1,
        experiment_cost=0.0,
    )
    assert positive.structural_validity_passed
    assert negative.structural_validity_passed is False
    assert report.passed
    assert report.false_structure_promotion_rate == 0.0


def test_ieee_acceptance_names_behavioral_proxy_not_validated_uid() -> None:
    acceptance = IEEERunAcceptance(1, 3, 1, True, frozenset({"lightgbm", "logistic"}), 3, 1, 1)
    assert acceptance.validated_behavioral_client_proxies == 1
    assert acceptance.validated_uid_candidates == 1
    assert acceptance.passed
