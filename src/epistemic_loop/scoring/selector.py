from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Literal

from epistemic_loop.config import PhaseWeights
from epistemic_loop.controller.mode_policy import capabilities
from epistemic_loop.domain.enums import Risk, RunMode, StructuralDimension
from epistemic_loop.domain.models import ExperimentProposal
from epistemic_loop.domain.validation import GateContext, GateResult, hard_gate
from epistemic_loop.scoring.cost import normalized_cost
from epistemic_loop.scoring.diversity import diversity_value, experiment_similarity
from epistemic_loop.scoring.epistemic import epistemic_value_v1, epistemic_value_v2, evsi_proxy_value
from epistemic_loop.scoring.pragmatic import robust_score_gain
from epistemic_loop.scoring.robustness import robustness_value


@dataclass(frozen=True)
class UtilityBreakdown:
    #: Expected score gain rescaled to [0, 1] against the other candidates in the same decision.
    #: The other three components are rubric scores already on that scale; leaving this one in the
    #: metric's own units makes the weighted sum a function of the metric's magnitude rather than
    #: of the weights. On a competition scored in ROC AUC the raw gains are ~0.01 and the four
    #: terms stay comparable by accident. On one scored in feet, the first measured gain was 11336
    #: against rubric scores below 1, so `epistemic: 0.45` -- the weight that makes a discovery
    #: phase a discovery phase -- moved the total by less than one part in five thousand.
    pragmatic: float
    epistemic: float
    eig: float
    evsi: float
    robustness: float
    diversity: float
    structural_leverage: float
    discrimination: float
    validation_debt_reduction: float
    cost: float
    risk: float
    total: float
    epistemic_method: str = "rubric_v1"
    #: The gain before rescaling, kept because the rescaled figure is only meaningful next to the
    #: candidates it was scaled against, and the record has to survive that context being lost.
    pragmatic_raw: float = 0.0


@dataclass(frozen=True)
class ScoredCandidate:
    proposal: ExperimentProposal
    gate: GateResult
    utility: UtilityBreakdown | None


def score_experiment(
    proposal: ExperimentProposal,
    weights: PhaseWeights,
    cost_lambda: float = 0.15,
    *,
    beliefs: Mapping[str, float] | None = None,
    mode: RunMode = RunMode.EPISTEMIC,
    risk_lambda: float = 0.5,
    eig_method: Literal["exact", "monte_carlo"] = "exact",
    eig_monte_carlo_samples: int = 4000,
    random_seed: int = 101,
    information_value_enabled: bool = True,
) -> UtilityBreakdown:
    policy = capabilities(mode)
    pragmatic = robust_score_gain(proposal.expected_score_gain)
    measured_epistemic = epistemic_value_v2(
        proposal.outcome_forecasts,
        beliefs or {},
        method=eig_method,
        monte_carlo_samples=eig_monte_carlo_samples,
        seed=random_seed,
    )
    if not policy.information_value or not information_value_enabled:
        eig = 0.0
        evsi = 0.0
        epistemic = 0.0
        epistemic_method = "disabled_by_system_mode" if not policy.information_value else "disabled_by_ablation"
    else:
        if measured_epistemic is None:
            eig = epistemic_value_v1(proposal.epistemic_assessment)
            epistemic_method = "rubric_v1"
        else:
            eig = measured_epistemic
            epistemic_method = (
                "expected_information_gain_v2" if eig_method == "exact" else "expected_information_gain_v2_monte_carlo"
            )
        measured_evsi = evsi_proxy_value(proposal.evsi_proxy)
        evsi = measured_evsi or 0.0
        if measured_evsi is not None:
            epistemic_method = "evsi_proxy"
        epistemic = evsi if measured_evsi is not None else eig
    robustness = (
        robustness_value(proposal.robustness_assessment)
        if mode not in {RunMode.SYSTEM_A, RunMode.EXPLOITER_ONLY}
        else 0.0
    )
    diversity = diversity_value(proposal) if policy.solution_qd else 0.0
    structural_leverage = min(1.0, proposal.structural_leverage / len(StructuralDimension))
    discrimination = proposal.robust_discrimination_value
    validation_debt_reduction = proposal.validation_debt_reduction
    cost = normalized_cost(proposal.estimated_cost)
    contamination = {Risk.LOW: 0.0, Risk.MEDIUM: 0.5, Risk.HIGH: 1.0}[proposal.contamination_risk]
    risk = min(1.0, proposal.estimated_cost.failure_probability + contamination)
    return _combine(
        UtilityBreakdown(
            pragmatic=pragmatic,
            epistemic=epistemic,
            eig=eig,
            evsi=evsi,
            robustness=robustness,
            diversity=diversity,
            structural_leverage=structural_leverage,
            discrimination=discrimination,
            validation_debt_reduction=validation_debt_reduction,
            cost=cost,
            risk=risk,
            total=0.0,
            epistemic_method=epistemic_method,
            pragmatic_raw=pragmatic,
        ),
        weights,
        cost_lambda,
        risk_lambda,
    )


def _relative_gain(values: list[float]) -> list[float]:
    """Rescale expected gains to [-1, 1] against the largest one in the same decision.

    Deliberately not min-max. Min-max spends the whole range on whatever spread happens to be
    present, so with two candidates promising 0.2 and 0.1 the second scores zero -- and a
    diagnostic that honestly forecasts no gain at all lands on 0 or 1 depending only on which
    neighbours it was compared against. Scaling by the largest magnitude keeps the ratios: equal
    forecasts score equally, a forecast of nothing scores nothing, and a candidate that expects to
    cost score keeps its negative sign.
    """
    largest = max((abs(value) for value in values), default=0.0)
    return [0.0 for _ in values] if largest == 0 else [value / largest for value in values]


def _combine(
    breakdown: UtilityBreakdown, weights: PhaseWeights, cost_lambda: float, risk_lambda: float
) -> UtilityBreakdown:
    total = (
        weights.pragmatic * breakdown.pragmatic
        + weights.epistemic * breakdown.epistemic
        + weights.robustness * breakdown.robustness
        + weights.diversity * breakdown.diversity
        + weights.structural_leverage * breakdown.structural_leverage
        + weights.discrimination * breakdown.discrimination
        + weights.validation_debt_reduction * breakdown.validation_debt_reduction
        - cost_lambda * breakdown.cost
        - risk_lambda * breakdown.risk
    )
    return replace(breakdown, total=total)


def evaluate_candidates(
    proposals: list[ExperimentProposal],
    context: GateContext,
    weights: PhaseWeights,
    cost_lambda: float = 0.15,
    *,
    beliefs: Mapping[str, float] | None = None,
    mode: RunMode = RunMode.EPISTEMIC,
    risk_lambda: float = 0.5,
    eig_method: Literal["exact", "monte_carlo"] = "exact",
    eig_monte_carlo_samples: int = 4000,
    random_seed: int = 101,
    information_value_enabled: bool = True,
) -> list[ScoredCandidate]:
    result = []
    for proposal in proposals:
        gate = hard_gate(proposal, context)
        utility = (
            score_experiment(
                proposal,
                weights,
                cost_lambda,
                beliefs=beliefs,
                mode=mode,
                risk_lambda=risk_lambda,
                eig_method=eig_method,
                eig_monte_carlo_samples=eig_monte_carlo_samples,
                random_seed=random_seed,
                information_value_enabled=information_value_enabled,
            )
            if gate.passed
            else None
        )
        result.append(ScoredCandidate(proposal, gate, utility))

    # Rescale the expected gain across the candidates actually being compared. Selection is a
    # ranking problem within one decision, so the question the pragmatic term should answer is
    # "which of these promises the most", not "how many units does it promise" -- and the units are
    # whatever the competition happens to measure in. Scaling here rather than in
    # `score_experiment` keeps that function honest for a single proposal, where there is nothing
    # to scale against and the raw number is the only truthful answer.
    scored = [(item, item.utility) for item in result if item.utility is not None]
    if len(scored) < 2:
        return result
    rescaled = _relative_gain([utility.pragmatic_raw for _, utility in scored])
    replacements = {
        id(item): _combine(replace(utility, pragmatic=value), weights, cost_lambda, risk_lambda)
        for (item, utility), value in zip(scored, rescaled, strict=True)
    }
    return [ScoredCandidate(item.proposal, item.gate, replacements.get(id(item), item.utility)) for item in result]


def select_portfolio(
    candidates: list[ScoredCandidate],
    size: int,
    *,
    similarity_penalty: float = 0.25,
    minimum_utility: float = float("-inf"),
    allocation: Mapping[str, float] | None = None,
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

        pool = remaining
        if allocation:
            counts = {name: 0 for name in allocation}
            for chosen in selected:
                bucket = experiment_bucket(chosen.proposal)
                counts[bucket] = counts.get(bucket, 0) + 1
            bucket = max(
                allocation,
                key=lambda name: (allocation[name] * (len(selected) + 1) - counts.get(name, 0), name),
            )
            matching = [item for item in remaining if experiment_bucket(item.proposal) == bucket]
            if matching:
                pool = matching
        best = max(pool, key=marginal)
        if marginal(best)[0] < minimum_utility:
            break
        selected.append(best)
        remaining.remove(best)
    return selected


def experiment_bucket(proposal: ExperimentProposal) -> str:
    from epistemic_loop.domain.enums import ExperimentType

    if proposal.experiment_type in {ExperimentType.EXPLOIT, ExperimentType.OPTIMIZATION}:
        return "exploit"
    if proposal.experiment_type in {
        ExperimentType.SOLUTION_EXPLORE,
        ExperimentType.ENSEMBLE,
        ExperimentType.ABLATION,
    }:
        return "qd_explore"
    return "epistemic"
