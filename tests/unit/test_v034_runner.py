from __future__ import annotations

import pytest

from epistemic_loop.benchmark.v034_outcome_only import (
    DiagnosticResourceObservation,
    OutcomeOnlyPlan,
    OutcomeRunRequest,
    OutcomeRunResult,
    SequentialOutcomeOnlyRunner,
)
from epistemic_loop.evaluation.v034 import V034RunOutputLock

DIGEST = "a" * 64


def _plan() -> OutcomeOnlyPlan:
    return OutcomeOnlyPlan.build(
        outer_seeds=range(12),
        dataset_sha256="d" * 64,
        fold_plan_sha256="f" * 64,
        row_set_sha256="r" * 64,
        prompt_sha256=DIGEST,
        research_opportunity_sha256=DIGEST,
        hidden_evaluator_sha256=DIGEST,
        acceptance_sha256=DIGEST,
        validation_constraint_sha256=DIGEST,
    )


def _callback(request: OutcomeRunRequest) -> OutcomeRunResult:
    lock = V034RunOutputLock.freeze(
        output_id=request.run_id,
        run_id=request.run_id,
        arm=request.arm,
        outer_seed=request.outer_seed,
        candidate_id=f"candidate-{request.run_id}",
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
        local_auc=0.9,
    )
    # Wildly different resources are legal and remain diagnostic-only.
    return OutcomeRunResult(
        lock,
        DiagnosticResourceObservation(
            cpu_seconds=float(request.outer_seed + 1) * (10 if request.arm.value == "C" else 1),
            peak_memory_bytes=10_000,
            wall_clock_seconds=5_000,
            llm_tokens=1_000_000,
        ),
    )


def test_outcome_plan_is_seed_paired_36_run_without_resource_budget() -> None:
    plan = _plan()
    assert len(plan.requests) == 36
    assert [item.arm.value for item in plan.requests[:3]] == ["B", "B_plus", "C"]
    assert all(item.agents == 3 and item.adaptive_cycles == 3 for item in plan.requests)
    assert plan.resource_policy.cpu_limit is None
    assert not plan.resource_policy.use_resource_in_acceptance
    assert plan.private_results_visible_during_run is False
    with pytest.raises(ValueError, match="12 unique"):
        OutcomeOnlyPlan.build(
            outer_seeds=(1, 2),
            dataset_sha256="d",
            fold_plan_sha256="f",
            row_set_sha256="r",
            prompt_sha256="p",
            research_opportunity_sha256="o",
            hidden_evaluator_sha256="h",
            acceptance_sha256="a",
            validation_constraint_sha256="v",
        )


def test_information_boundary_rejects_past_solution_evidence() -> None:
    plan = _plan()
    plan.validate_information_boundary({"dataset_schema": {}, "artifact_contract": {}})
    with pytest.raises(PermissionError, match="forbidden"):
        plan.validate_information_boundary({"evidence": {"past_private_score": 0.99}})


def test_complete_outcome_run_locks_without_resource_matching() -> None:
    result = SequentialOutcomeOnlyRunner().run(_plan(), _callback)
    assert result.completed_runs == 36
    assert not result.failures
    assert result.hidden_evaluation_ready
    assert result.sealed_batch is not None and result.sealed_batch.verify()
    assert not result.resource_metrics_used


def test_any_failed_run_keeps_hidden_batch_sealed() -> None:
    def fail_one(request: OutcomeRunRequest) -> OutcomeRunResult:
        if request.run_id == "B-0":
            raise RuntimeError("failed artifact")
        return _callback(request)

    result = SequentialOutcomeOnlyRunner().run(_plan(), fail_one)
    assert result.completed_runs == 35
    assert len(result.failures) == 1
    assert result.sealed_batch is None
    assert not result.hidden_evaluation_ready
