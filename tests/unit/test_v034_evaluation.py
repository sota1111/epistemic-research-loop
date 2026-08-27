from __future__ import annotations

from dataclasses import replace

import pytest

from epistemic_loop.evaluation.v032 import SystemArm
from epistemic_loop.evaluation.v034 import (
    ArmPolicyHash,
    DecisionChoice,
    DecisionLock,
    DecisionQualityAudit,
    FinalRetrainLock,
    FinalSelectionCandidate,
    LockedOutcomeScore,
    OutcomeOnlyResourcePolicy,
    SealedDecisionOutcome,
    V034Acceptance,
    V034ArmCapabilities,
    V034CandidateEligibility,
    V034CandidateEligibilityEvidence,
    V034Conclusion,
    V034FinalMetaSelector,
    V034RunOutputLock,
    V034SealedOutcomeBatch,
    V034Status,
    classify_outcome_conclusion,
    evaluate_outcome_batch,
)

DIGEST = "a" * 64


def _output(arm: SystemArm, seed: int, *, local_auc: float = 0.9) -> V034RunOutputLock:
    return V034RunOutputLock.freeze(
        output_id=f"{arm.value}-{seed}",
        run_id=f"{arm.value}-{seed}",
        arm=arm,
        outer_seed=seed,
        candidate_id=f"candidate-{arm.value}-{seed}",
        base_commit="ac3b46975e5da64570fb79d6e1141bc5c7525d0f",
        dataset_sha256="d" * 64,
        fold_plan_sha256="f" * 64,
        row_set_sha256="r" * 64,
        candidate_commit="c" * 40,
        feature_manifest_sha256=DIGEST,
        selection_rule_sha256=DIGEST,
        test_prediction_sha256=DIGEST,
        submission_sha256=DIGEST,
        sealed_prediction_sha256=DIGEST,
        final_retrain_lock_sha256=DIGEST,
        cycle_decision_lock_sha256=(DIGEST,) * 9,
        local_auc=local_auc,
    )


def _batch() -> V034SealedOutcomeBatch:
    outputs = [_output(arm, seed, local_auc=0.88 + seed / 10_000) for seed in range(12) for arm in SystemArm]
    policies = tuple(ArmPolicyHash(arm, str(index) * 64) for index, arm in enumerate(SystemArm, start=1))
    return V034SealedOutcomeBatch.freeze(
        outputs,
        arm_policy_hashes=policies,
        prompt_sha256=DIGEST,
        acceptance_sha256=DIGEST,
        validation_constraint_sha256=DIGEST,
        plan_sha256=DIGEST,
        hidden_evaluator_sha256=DIGEST,
    )


def test_arm_policy_adds_predictive_then_epistemic_terms_without_cost() -> None:
    b = V034ArmCapabilities.for_arm(SystemArm.B)
    b_plus = V034ArmCapabilities.for_arm(SystemArm.B_PLUS)
    c = V034ArmCapabilities.for_arm(SystemArm.C)

    assert not b.predictive_slice_preregistration
    assert b_plus.predictive_slice_preregistration and not b_plus.hypothesis_registry
    assert c.hypothesis_registry and c.falsification and c.belief_update
    assert all("cost" not in term for term in c.utility_terms)
    with pytest.raises(ValueError, match="forbids resource"):
        OutcomeOnlyResourcePolicy(use_resource_in_selection=True)


def test_standalone_and_ensemble_eligibility_are_independent() -> None:
    evidence = V034CandidateEligibilityEvidence(
        True,
        True,
        True,
        True,
        True,
        0.89,
        0.90,
        0.002,
        2,
        3,
        0.6,
    )
    result = V034CandidateEligibility.assess(evidence)
    assert not result.standalone
    assert result.ensemble


def test_meta_selector_rejects_ensemble_without_gain() -> None:
    candidates = (
        FinalSelectionCandidate("a", (), False, 0.91, 0.89, 0.002, True, False, True, DIGEST),
        FinalSelectionCandidate("b", (), False, 0.90, 0.895, 0.001, True, False, True, DIGEST),
        FinalSelectionCandidate("bad-blend", ("a", "b"), True, 0.909, 0.90, 0.001, False, True, True, DIGEST),
        FinalSelectionCandidate("good-blend", ("a", "b"), True, 0.912, 0.90, 0.001, False, True, True, DIGEST),
    )
    selected = V034FinalMetaSelector().select(candidates)
    assert selected.candidate_id == "good-blend"


def test_final_retrain_is_full_deterministic_and_sealed_independent() -> None:
    lock = FinalRetrainLock.freeze(
        candidate_id="good-blend",
        pipeline_source_sha256=DIGEST,
        feature_manifest_sha256=DIGEST,
        hyperparameters_sha256=DIGEST,
        ensemble_weights_sha256=DIGEST,
    )
    assert lock.verify()
    with pytest.raises(ValueError, match="sealed outcomes"):
        FinalRetrainLock.freeze(
            candidate_id="good-blend",
            pipeline_source_sha256=DIGEST,
            feature_manifest_sha256=DIGEST,
            hyperparameters_sha256=DIGEST,
            ensemble_weights_sha256=DIGEST,
            sealed_dependent_changes=True,
        )


def test_decision_audit_measures_false_rejection_adoption_and_regret() -> None:
    first = DecisionLock.freeze(
        decision_id="d1",
        run_id="run",
        agent_id="a",
        cycle=1,
        parent_id="p1",
        challenger_id="c1",
        local_parent_auc=0.91,
        local_challenger_auc=0.90,
        local_selected=DecisionChoice.PARENT,
        minimum_gain=0.001,
        stability_condition="two horizons",
        rejection_condition="negative gain",
        parent_prediction_sha256=DIGEST,
        challenger_prediction_sha256=DIGEST,
    )
    second = DecisionLock.freeze(
        decision_id="d2",
        run_id="run",
        agent_id="a",
        cycle=2,
        parent_id="p2",
        challenger_id="c2",
        local_parent_auc=0.90,
        local_challenger_auc=0.91,
        local_selected=DecisionChoice.CHALLENGER,
        minimum_gain=0.001,
        stability_condition="two horizons",
        rejection_condition="negative gain",
        parent_prediction_sha256=DIGEST,
        challenger_prediction_sha256=DIGEST,
    )
    audit = DecisionQualityAudit.assess(
        (first, second),
        (
            SealedDecisionOutcome("d1", 0.90, 0.92),
            SealedDecisionOutcome("d2", 0.93, 0.91),
        ),
    )
    assert audit.decision_sign_accuracy == 0
    assert audit.false_rejection_rate == 0.5
    assert audit.false_adoption_rate == 0.5
    assert audit.total_selection_regret == pytest.approx(0.04)


def test_sealed_batch_requires_all_36_common_hash_outputs() -> None:
    batch = _batch()
    assert batch.verify()
    with pytest.raises(ValueError, match="12 outputs"):
        V034SealedOutcomeBatch.freeze(
            batch.outputs[:-1],
            arm_policy_hashes=batch.arm_policy_hashes,
            prompt_sha256=DIGEST,
            acceptance_sha256=DIGEST,
            validation_constraint_sha256=DIGEST,
            plan_sha256=DIGEST,
            hidden_evaluator_sha256=DIGEST,
        )
    changed = list(batch.outputs)
    changed[-1] = replace(changed[-1], fold_plan_sha256="x" * 64)
    with pytest.raises(ValueError, match="output locks are invalid"):
        V034SealedOutcomeBatch.freeze(
            changed,
            arm_policy_hashes=batch.arm_policy_hashes,
            prompt_sha256=DIGEST,
            acceptance_sha256=DIGEST,
            validation_constraint_sha256=DIGEST,
            plan_sha256=DIGEST,
            hidden_evaluator_sha256=DIGEST,
        )


def test_complete_hidden_batch_reports_paired_outcomes_and_capability_pass() -> None:
    batch = _batch()
    scores = []
    for output in batch.outputs:
        offset = output.outer_seed * 0.00001
        private = {SystemArm.B: 0.900, SystemArm.B_PLUS: 0.905, SystemArm.C: 0.908}[output.arm] + offset
        regret = {SystemArm.B: 0.004, SystemArm.B_PLUS: 0.003, SystemArm.C: 0.001}[output.arm]
        scores.append(
            LockedOutcomeScore(
                output_id=output.output_id,
                private_auc=private,
                sealed_future_auc=private - 0.001,
                run_selection_regret=regret,
                nested_ensemble_gain=0.001,
                hidden_ensemble_gain=0.001,
                validated_structures=1,
                false_structure_promotions=0,
                global_validation_constraints_discovered=1,
                independent_replications=2,
                redundant_duplications=1,
                artifact_completed=True,
                valid_submission=True,
            )
        )
    audits = {
        output.output_id: DecisionQualityAudit(9, 1.0, 0.0, 0.0, 0.0, 0.0, ())
        for output in batch.outputs
    }
    with pytest.raises(ValueError, match="cover all"):
        evaluate_outcome_batch(batch, scores[:-1], audits, bootstrap_iterations=200)

    analysis = evaluate_outcome_batch(batch, scores, audits, bootstrap_iterations=500)
    acceptance = V034Acceptance.from_outcomes(
        analysis,
        semantic_diversity=V034Status.PASS,
        quality_predictive_diversity=V034Status.PASS,
        structure_falsification=V034Status.PASS,
        true_structure_discovery=V034Status.PASS,
    )

    assert analysis.paired_seeds == 12
    assert analysis.c_vs_b_plus.mean_delta == pytest.approx(0.003)
    assert analysis.c_vs_b_plus.bootstrap_ci_95[0] > 0
    assert acceptance.unrestricted_outcome_advantage_over_b is V034Status.PASS
    assert acceptance.unrestricted_outcome_advantage_over_b_plus is V034Status.PASS
    assert classify_outcome_conclusion(analysis) is V034Conclusion.FULL_C_CAPABILITY
    assert not analysis.resource_metrics_used

    b_plus_sufficient = replace(
        analysis,
        c_vs_b_plus=replace(
            analysis.c_vs_b_plus,
            mean_delta=0.0002,
            median_delta=0.0002,
            bootstrap_ci_95=(-0.0001, 0.0005),
        ),
    )
    assert classify_outcome_conclusion(b_plus_sufficient) is V034Conclusion.B_PLUS_SUFFICIENT

    strong_b = replace(
        analysis,
        c_vs_b=replace(analysis.c_vs_b, mean_delta=0.0002, median_delta=0.0002),
        c_vs_b_plus=replace(
            analysis.c_vs_b_plus,
            mean_delta=0.0001,
            median_delta=0.0001,
            bootstrap_ci_95=(-0.0001, 0.0003),
        ),
        b_plus_vs_b=replace(analysis.b_plus_vs_b, mean_delta=0.0001, median_delta=0.0001),
    )
    assert classify_outcome_conclusion(strong_b) is V034Conclusion.STRONG_B_SUFFICIENT

    c_rejected = replace(
        analysis,
        c_vs_b_plus=replace(
            analysis.c_vs_b_plus,
            mean_delta=-0.002,
            median_delta=-0.002,
            bootstrap_ci_95=(-0.003, -0.001),
        ),
    )
    assert classify_outcome_conclusion(c_rejected) is V034Conclusion.C_REJECTED
