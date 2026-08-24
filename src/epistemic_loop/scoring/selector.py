from __future__ import annotations

from dataclasses import dataclass

from epistemic_loop.config import PhaseWeights
from epistemic_loop.domain.models import ExperimentProposal
from epistemic_loop.domain.validation import GateContext, GateResult, hard_gate
from epistemic_loop.scoring.cost import normalized_cost
from epistemic_loop.scoring.diversity import diversity_value, experiment_similarity
from epistemic_loop.scoring.epistemic import epistemic_value_v1
from epistemic_loop.scoring.pragmatic import robust_score_gain
from epistemic_loop.scoring.robustness import robustness_value


@dataclass(frozen=True)
class UtilityBreakdown:
    pragmatic: float
    epistemic: float
    robustness: float
    diversity: float
    cost: float
    total: float


@dataclass(frozen=True)
class ScoredCandidate:
    proposal: ExperimentProposal
    gate: GateResult
    utility: UtilityBreakdown | None


def score_experiment(
    proposal: ExperimentProposal,
    weights: PhaseWeights,
    cost_lambda: float = 0.15,
) -> UtilityBreakdown:
    pragmatic = robust_score_gain(proposal.expected_score_gain)
    epistemic = epistemic_value_v1(proposal.epistemic_assessment)
    robustness = robustness_value(proposal.robustness_assessment)
    diversity = diversity_value(proposal)
    cost = normalized_cost(proposal.estimated_cost)
    total = (
        weights.pragmatic * pragmatic
        + weights.epistemic * epistemic
        + weights.robustness * robustness
        + weights.diversity * diversity
        - cost_lambda * cost
    )
    return UtilityBreakdown(pragmatic, epistemic, robustness, diversity, cost, total)


def evaluate_candidates(
    proposals: list[ExperimentProposal],
    context: GateContext,
    weights: PhaseWeights,
    cost_lambda: float = 0.15,
) -> list[ScoredCandidate]:
    result = []
    for proposal in proposals:
        gate = hard_gate(proposal, context)
        utility = score_experiment(proposal, weights, cost_lambda) if gate.passed else None
        result.append(ScoredCandidate(proposal, gate, utility))
    return result


def select_portfolio(
    candidates: list[ScoredCandidate],
    size: int,
    *,
    similarity_penalty: float = 0.25,
    minimum_utility: float = float("-inf"),
) -> list[ScoredCandidate]:
    """Greedy maximum-marginal-utility portfolio, not a naive top-K list."""
    eligible = [item for item in candidates if item.gate.passed and item.utility is not None]
    selected: list[ScoredCandidate] = []
    remaining = eligible[:]
    while remaining and len(selected) < size:

        def marginal(item: ScoredCandidate) -> tuple[float, str]:
            assert item.utility is not None
            similarity = max(
                (experiment_similarity(item.proposal, chosen.proposal) for chosen in selected),
                default=0.0,
            )
            return item.utility.total - similarity_penalty * similarity, item.proposal.id

        best = max(remaining, key=marginal)
        if marginal(best)[0] < minimum_utility:
            break
        selected.append(best)
        remaining.remove(best)
    return selected
