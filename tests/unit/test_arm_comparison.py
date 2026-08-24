from __future__ import annotations

from epistemic_loop.controller.run_state import RunState
from epistemic_loop.domain.enums import (
    ExperimentStatus,
    ExperimentType,
    FalsificationDisposition,
    HypothesisStatus,
    LoopState,
    Phase,
    RunMode,
    RunStatus,
)
from epistemic_loop.domain.models import (
    BudgetUsage,
    ExperimentProposal,
    FalsificationRecord,
    Hypothesis,
    Observation,
    ResearchRun,
)
from epistemic_loop.reporting.arm_comparison import arm_summary, build_arm_comparison


def _run(run_id: str, mode: RunMode) -> ResearchRun:
    return ResearchRun(
        id=run_id,
        competition_id="ieee-fraud-detection",
        mode=mode,
        seed=101,
        status=RunStatus.RUNNING,
        base_commit_sha="abc123",
        dataset_fingerprint="f" * 64,
        config_hash="c" * 64,
    )


def _observation(experiment_id: str, score: float) -> Observation:
    return Observation(
        id=f"OB-{experiment_id}",
        experiment_id=experiment_id,
        run_id="run",
        metrics={"roc_auc": score},
        code_commit_sha="abc123",
        environment_hash="e" * 64,
        dataset_fingerprint="f" * 64,
        exit_status="completed",
    )


def _state(
    run_id: str,
    mode: RunMode,
    proposals: list[ExperimentProposal],
    hypotheses: list[Hypothesis],
    observations: list[Observation],
    falsifications: list[FalsificationRecord],
) -> RunState:
    return RunState(
        run=_run(run_id, mode),
        loop_state=LoopState.PLANNING,
        phase=Phase.DISCOVERY,
        hypotheses={item.id: item for item in hypotheses},
        proposals={item.id: item for item in proposals},
        experiment_statuses={item.id: ExperimentStatus.COMPLETED for item in proposals},
        observations={item.id: item for item in observations},
        falsifications={item.id: item for item in falsifications},
        usage=BudgetUsage(cpu_hours=12.85),
        selection_order=tuple(item.id for item in proposals),
        violations=0,
    )


def test_the_summary_separates_scoring_from_non_scoring_work(
    hypothesis: Hypothesis,
    proposal: ExperimentProposal,
    clone_proposal,
) -> None:
    """The share of the budget spent on experiments that cannot raise the metric is the cost of research.

    It is also the number that makes two arms comparable at all: an arm that spends nothing on
    diagnostics and an arm that spends most of its budget there are not doing the same activity, and
    a table that reports only their scores hides that.
    """
    proposals = [
        clone_proposal(proposal, id="E-DIAG", experiment_type=ExperimentType.DIAGNOSTIC, lineage="validation"),
        clone_proposal(proposal, id="E-ABL", experiment_type=ExperimentType.ABLATION, lineage="representation"),
        clone_proposal(proposal, id="E-OPT", experiment_type=ExperimentType.OPTIMIZATION, lineage="gbdt"),
    ]
    observations = [_observation("E-DIAG", 0.90), _observation("E-OPT", 0.96)]
    summary = arm_summary(
        _state("epistemic", RunMode.EPISTEMIC, proposals, [hypothesis], observations, []),
        submissions=1,
        public_score=0.935,
        steering_estimate=0.96,
    )

    assert summary["experiments_completed"] == 3
    assert summary["non_scoring_share"] == round(2 / 3, 3)
    assert summary["distinct_lineages"] == 3
    assert summary["best_local_roc_auc"] == 0.96
    assert summary["steering_estimate"] == 0.96
    assert summary["cv_public_gap"] == 0.025
    assert summary["kaggle_submissions"] == 1


def test_refutation_is_counted_separately_from_confirmation(
    hypothesis: Hypothesis,
    proposal: ExperimentProposal,
    clone_proposal,
) -> None:
    """An arm that only ever confirms itself should not look the same as one that overturns claims."""
    falsified = hypothesis.model_copy(update={"id": "H-DEAD", "status": HypothesisStatus.FALSIFIED, "version": 2})
    contested = hypothesis.model_copy(update={"id": "H-DOUBT", "status": HypothesisStatus.CONTESTED, "version": 2})
    supported = hypothesis.model_copy(update={"id": "H-OK", "status": HypothesisStatus.SUPPORTED, "version": 2})
    record = FalsificationRecord(
        id="FR-1",
        hypothesis_id="H-DEAD",
        observation_ids=["OB-E-DIAG"],
        strongest_alternative_explanation="none",
        confounders_checked=[],
        supporting_predictions_matched=[],
        contradicting_predictions_matched=["the effect did not appear"],
        disposition=FalsificationDisposition.FALSIFIED,
    )
    summary = arm_summary(
        _state(
            "epistemic",
            RunMode.EPISTEMIC,
            [clone_proposal(proposal, id="E-DIAG", experiment_type=ExperimentType.DIAGNOSTIC)],
            [falsified, contested, supported],
            [_observation("E-DIAG", 0.9)],
            [record],
        )
    )
    assert summary["refuted"] == 2, "falsified and contested both count as refutation"
    assert summary["falsification_dispositions"] == {"falsified": 1}
    assert summary["public_score"] is None and summary["cv_public_gap"] is None


def test_the_report_refuses_to_present_local_scores_as_comparable(
    hypothesis: Hypothesis,
    proposal: ExperimentProposal,
    clone_proposal,
) -> None:
    """Each arm chose its own validation scheme, so its local number is not the other's number.

    The report has to say so in the body, because a reader scanning a two-column table will
    otherwise read the higher local score as the better result -- which is exactly backwards when
    the higher number came from the more optimistic split.
    """
    left = arm_summary(
        _state(
            "epistemic",
            RunMode.EPISTEMIC,
            [clone_proposal(proposal, id="E-DIAG", experiment_type=ExperimentType.DIAGNOSTIC)],
            [hypothesis],
            [_observation("E-DIAG", 0.9101)],
            [],
        ),
        public_score=0.935,
        steering_estimate=0.9101,
    )
    right = arm_summary(
        _state(
            "exploiter",
            RunMode.EXPLOITER_ONLY,
            [clone_proposal(proposal, id="E-OPT", experiment_type=ExperimentType.OPTIMIZATION)],
            [hypothesis],
            [_observation("E-OPT", 0.9708)],
            [],
        ),
        public_score=0.935,
        steering_estimate=0.9708,
    )
    report = build_arm_comparison(left, right, notes=["one submission per arm"])

    assert "not comparable to each other" in report
    assert "one submission per arm" in report
    # The signs must survive into the report: the researcher under-claimed, the exploiter over-claimed.
    assert "-0.0249" in report
    assert "0.0358" in report
    assert "sign" in report
