from __future__ import annotations

from epistemic_loop.controller.budget_manager import BudgetManager
from epistemic_loop.controller.run_state import RunState
from epistemic_loop.domain.enums import (
    Consequence,
    ExperimentStatus,
    HypothesisStatus,
    HypothesisType,
)
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


def derive_brief(
    state: RunState,
    *,
    primary_metric: str,
    validation_scheme: dict[str, object] | None = None,
) -> ResearchBrief:
    """Build the exploiter hand-off from the event-log fold alone.

    Everything here is already in the record: which hypotheses survived, which split the surviving
    validation hypothesis endorses, which lineages produced completed evidence, and what remains
    unresolved. Deriving it rather than asking for it is what makes the hand-off checkable — the
    exploiter receives the run's conclusions, not a fresh summary that could quietly add a claim.
    """
    hypotheses = list(state.hypotheses.values())
    supported_validation = [
        item
        for item in hypotheses
        if item.type == HypothesisType.VALIDATION and item.status == HypothesisStatus.SUPPORTED
    ]
    scheme: dict[str, object] = dict(validation_scheme or {})
    if not scheme:
        scheme = {
            "source": "supported validation hypotheses",
            "hypothesis_ids": [item.id for item in supported_validation],
            "claims": [item.claim for item in supported_validation],
            "split_strategies": sorted(
                {
                    state.proposals[identifier].split_strategy
                    for identifier in state.proposals
                    if state.experiment_statuses.get(identifier) == ExperimentStatus.COMPLETED
                    and any(item.id in state.proposals[identifier].hypothesis_ids for item in supported_validation)
                }
            ),
        }
    if not scheme.get("split_strategies") and not validation_scheme:
        raise ValueError("no completed experiment established a validation scheme; the hand-off would be unsupported")

    supported_ids = {item.id for item in hypotheses if item.status == HypothesisStatus.SUPPORTED}
    approved_lineages = sorted(
        {
            proposal.lineage
            for identifier, proposal in state.proposals.items()
            if state.experiment_statuses.get(identifier) == ExperimentStatus.COMPLETED
            and supported_ids.intersection(proposal.hypothesis_ids)
        }
    )
    approved_features = sorted(
        {
            item.scope
            for item in hypotheses
            if item.status == HypothesisStatus.SUPPORTED
            and item.type in {HypothesisType.FEATURE_FAMILY, HypothesisType.REPRESENTATION}
        }
    )
    search_ranges: dict[str, object] = {
        "lineages": approved_lineages,
        "seeds": sorted({seed for proposal in state.proposals.values() for seed in proposal.seeds}),
        "metrics": sorted({metric for proposal in state.proposals.values() for metric in proposal.metrics}),
        "validation_reuse_spent": state.validation_reuse(),
    }
    return synthesize_research_brief(
        state.run_id,
        hypotheses,
        BudgetManager(state.run.budgets, state.usage),
        validation_scheme=scheme,
        primary_metric=primary_metric,
        approved_feature_families=approved_features,
        approved_model_lineages=approved_lineages,
        search_ranges=search_ranges,
    )
