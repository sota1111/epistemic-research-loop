from __future__ import annotations

from epistemic_loop.controller.budget_manager import BudgetManager
from epistemic_loop.domain.enums import Consequence, HypothesisStatus
from epistemic_loop.domain.models import Hypothesis, ResearchBrief


def synthesize_research_brief(
    run_id: str,
    hypotheses: list[Hypothesis],
    budget_manager: BudgetManager,
    *,
    validation_scheme: dict[str, object],
    primary_metric: str,
    approved_feature_families: list[str],
    approved_model_lineages: list[str],
    search_ranges: dict[str, object],
) -> ResearchBrief:
    supported = [item.id for item in hypotheses if item.status == HypothesisStatus.SUPPORTED]
    falsified = [item.id for item in hypotheses if item.status == HypothesisStatus.FALSIFIED]
    unresolved = [
        item.id
        for item in hypotheses
        if item.downstream_consequence in {Consequence.HIGH, Consequence.CRITICAL}
        and item.status not in {HypothesisStatus.SUPPORTED, HypothesisStatus.FALSIFIED, HypothesisStatus.RETIRED}
    ]
    return ResearchBrief(
        run_id=run_id,
        locked_validation_scheme=validation_scheme,
        primary_metric=primary_metric,
        robust_metric=f"robust_{primary_metric}",
        supported_hypotheses=supported,
        falsified_hypotheses=falsified,
        unresolved_high_risk_hypotheses=unresolved,
        approved_feature_families=approved_feature_families,
        approved_model_lineages=approved_model_lineages,
        prohibited_shortcuts=["sealed holdout optimization", "public leaderboard feedback"],
        required_robustness_checks=["multiple seeds", "fold consistency", "subgroup worst-case"],
        search_ranges=search_ranges,
        remaining_budget=budget_manager.remaining(),
        expected_failure_modes=["seed instability", "split rank reversal", "unexpected distribution shift"],
    )
