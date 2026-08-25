from __future__ import annotations

from collections import Counter
from typing import Any

from epistemic_loop.controller.budget_manager import BudgetManager
from epistemic_loop.controller.run_state import RunState
from epistemic_loop.domain.enums import ExperimentStatus, FalsificationDisposition, HypothesisStatus
from epistemic_loop.scoring.normalization import higher_is_better

#: Experiment types that cannot raise the metric. Their share is what "research" costs.
NON_SCORING_TYPES = frozenset({"diagnostic", "falsification", "replication", "robustness", "ablation"})


def arm_summary(  # noqa: PLR0913
    state: RunState,
    *,
    primary_metric: str,
    metric_direction: str,
    submissions: int = 0,
    public_score: float | None = None,
    steering_estimate: float | None = None,
) -> dict[str, Any]:
    """Everything about one arm that a comparison should weigh, not just its score.

    Two arms that reach the same leaderboard position have not done the same work if one of them
    also knows why. The counts below are what makes that difference visible: how the budget was
    split between scoring and non-scoring experiments, how many claims were refuted rather than
    confirmed, and how far the arm's own local number was from the only hidden measurement it got.
    """
    hypotheses = list(state.hypotheses.values())
    statuses = Counter(item.status.value for item in hypotheses)
    dispositions = Counter(record.disposition.value for record in state.falsifications.values())
    completed = [
        proposal
        for identifier, proposal in state.proposals.items()
        if state.experiment_statuses.get(identifier) == ExperimentStatus.COMPLETED
    ]
    types = Counter(proposal.experiment_type.value for proposal in completed)
    non_scoring = sum(count for kind, count in types.items() if kind in NON_SCORING_TYPES)

    # The best number the arm ever saw, under *any* scheme. For an exploiter this is also the
    # number it steered by; for a research arm it is usually from a scheme the arm went on to
    # reject, so it must never be used as the arm's own estimate.
    #
    # "Best" depends on which way the metric runs, and this used to assume roc_auc and a maximum.
    # Pointed at a minimised competition it reported the arm's *worst* result as its best, and
    # nothing about the output looked wrong.
    observed = [
        observation.metrics[primary_metric]
        for observation in state.observations.values()
        if primary_metric in observation.metrics
    ]
    best_local_value = (
        max(observed, key=lambda value: higher_is_better(value, metric_direction)) if observed else None
    )
    return {
        "run_id": state.run_id,
        "mode": state.run.mode.value,
        "phase": state.phase.value,
        "experiments_completed": len(completed),
        "experiment_types": dict(sorted(types.items())),
        "non_scoring_share": round(non_scoring / len(completed), 3) if completed else 0.0,
        "hypotheses_total": len(hypotheses),
        "hypothesis_statuses": dict(sorted(statuses.items())),
        "refuted": statuses.get(HypothesisStatus.FALSIFIED.value, 0)
        + statuses.get(HypothesisStatus.CONTESTED.value, 0),
        "falsification_dispositions": dict(sorted(dispositions.items())),
        "inconclusive_experiments": dispositions.get(FalsificationDisposition.INCONCLUSIVE.value, 0),
        "cpu_hours": round(state.usage.cpu_hours, 2),
        "kaggle_submissions": submissions,
        "primary_metric": primary_metric,
        "metric_direction": metric_direction,
        "best_local_score": best_local_value,
        # The estimate the arm actually made decisions against. It has to be supplied, not inferred:
        # an arm that deliberately measures pessimistic schemes has a best-ever number that is not
        # its belief about itself, and computing the calibration gap from that number is meaningless.
        "steering_estimate": steering_estimate,
        "public_score": public_score,
        # Signed so that positive always means "the local estimate looked better than the
        # leaderboard did", in either direction. A raw subtraction reverses that meaning the moment
        # the metric is minimised, which is the kind of error a report is least likely to survive.
        "cv_public_gap": (
            round(
                higher_is_better(steering_estimate, metric_direction)
                - higher_is_better(public_score, metric_direction),
                4,
            )
            if steering_estimate is not None and public_score is not None
            else None
        ),
        "distinct_lineages": len({proposal.lineage for proposal in completed}),
        "violations": state.violations,
        "remaining_budget": BudgetManager(state.run.budgets, state.usage).remaining(),
    }


def _row(label: str, left: Any, right: Any) -> str:
    return f"| {label} | {left} | {right} |"


def build_arm_comparison(epistemic: dict[str, Any], exploiter: dict[str, Any], *, notes: list[str]) -> str:
    """Render the paired comparison. Private scores are never an input here."""
    lines = [
        "# Arm comparison",
        "",
        f"`{epistemic['run_id']}` (epistemic) against `{exploiter['run_id']}` (exploiter-only), "
        "same data, worker, seeds, budget and submission allowance.",
        "",
        "| Measure | Epistemic | Exploiter-only |",
        "| --- | ---: | ---: |",
        _row("Experiments completed", epistemic["experiments_completed"], exploiter["experiments_completed"]),
        _row("Non-scoring share of experiments", epistemic["non_scoring_share"], exploiter["non_scoring_share"]),
        _row("Distinct lineages explored", epistemic["distinct_lineages"], exploiter["distinct_lineages"]),
        _row("CPU hours", epistemic["cpu_hours"], exploiter["cpu_hours"]),
        _row("Kaggle submissions", epistemic["kaggle_submissions"], exploiter["kaggle_submissions"]),
        _row("Hypotheses held", epistemic["hypotheses_total"], exploiter["hypotheses_total"]),
        _row("Hypotheses refuted or contested", epistemic["refuted"], exploiter["refuted"]),
        _row(
            "Inconclusive verdicts recorded",
            epistemic["inconclusive_experiments"],
            exploiter["inconclusive_experiments"],
        ),
        _row("Best local number seen, any scheme", epistemic["best_local_score"], exploiter["best_local_score"]),
        _row("Estimate the arm steered by", epistemic["steering_estimate"], exploiter["steering_estimate"]),
        _row("Public leaderboard score", epistemic["public_score"], exploiter["public_score"]),
        _row("Calibration gap (steering minus public)", epistemic["cv_public_gap"], exploiter["cv_public_gap"]),
        _row("Holdout or rule violations", epistemic["violations"], exploiter["violations"]),
        "",
        "**The local scores are not comparable to each other.** Each arm reports the number produced by",
        "the validation scheme it chose, and choosing that scheme is part of what is being compared.",
        "",
        "The calibration gap is the row that can be read directly: each arm's own steering estimate minus",
        "the same kind of hidden measurement. Its **sign** matters as much as its size -- a positive gap",
        "means the arm believed it was better than it was, which is the direction that costs rank when the",
        "hidden split finally arrives.",
        "",
        "## Experiment mix",
        "",
        "| Type | Epistemic | Exploiter-only |",
        "| --- | ---: | ---: |",
    ]
    for kind in sorted(set(epistemic["experiment_types"]) | set(exploiter["experiment_types"])):
        lines.append(_row(kind, epistemic["experiment_types"].get(kind, 0), exploiter["experiment_types"].get(kind, 0)))
    lines.extend(["", "## Hypothesis outcomes", "", "| Status | Epistemic | Exploiter-only |", "| --- | ---: | ---: |"])
    for status in sorted(set(epistemic["hypothesis_statuses"]) | set(exploiter["hypothesis_statuses"])):
        lines.append(
            _row(
                status,
                epistemic["hypothesis_statuses"].get(status, 0),
                exploiter["hypothesis_statuses"].get(status, 0),
            )
        )
    if notes:
        lines.extend(["", "## Notes", ""])
        lines.extend(f"- {note}" for note in notes)
    return "\n".join(lines) + "\n"
