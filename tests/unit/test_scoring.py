import pytest

from epistemic_loop.config import PhaseWeights
from epistemic_loop.domain.models import (
    Budget,
    BudgetUsage,
    ExperimentProposal,
    HypothesisOutcomeForecast,
    OutcomeLikelihood,
)
from epistemic_loop.domain.validation import GateContext
from epistemic_loop.scoring.epistemic import binary_hypothesis_information_gain
from epistemic_loop.scoring.selector import evaluate_candidates, score_experiment, select_portfolio

WEIGHTS = PhaseWeights(pragmatic=0.2, epistemic=0.45, robustness=0.2, diversity=0.15)


def _context() -> GateContext:
    return GateContext(
        hypothesis_ids=frozenset({"H-001"}),
        budget=Budget(),
        usage=BudgetUsage(),
        holdout_policy="strict_blind",  # type: ignore[arg-type]
    )


def test_utility_uses_epistemic_value(proposal: ExperimentProposal) -> None:
    score = score_experiment(proposal, WEIGHTS)
    assert score.epistemic == 0.95
    assert score.epistemic_method == "rubric_v1"
    assert score.total > 0


def test_likelihood_forecast_replaces_self_scored_epistemic_rubric(proposal: ExperimentProposal) -> None:
    forecast = HypothesisOutcomeForecast(
        hypothesis_id="H-001",
        outcomes=[
            OutcomeLikelihood(label="rank_reversal", probability_if_true=0.9, probability_if_false=0.1),
            OutcomeLikelihood(label="stable_ranking", probability_if_true=0.1, probability_if_false=0.9),
        ],
        decisions_affected=["lock time validation"],
        measurement_notes="same candidate models and seeds under both splits",
    )
    candidate = proposal.model_copy(update={"outcome_forecasts": [forecast]})

    score = score_experiment(candidate, WEIGHTS, beliefs={"H-001": 0.5})

    assert score.epistemic == pytest.approx(0.5310044064)
    assert score.epistemic_method == "expected_information_gain_v2"
    assert score.epistemic != proposal.epistemic_assessment.score


def test_information_gain_is_zero_when_outcomes_do_not_discriminate() -> None:
    forecast = HypothesisOutcomeForecast(
        hypothesis_id="H-001",
        outcomes=[
            OutcomeLikelihood(label="up", probability_if_true=0.5, probability_if_false=0.5),
            OutcomeLikelihood(label="down", probability_if_true=0.5, probability_if_false=0.5),
        ],
        decisions_affected=["none until replicated"],
        measurement_notes="equal likelihoods are intentionally uninformative",
    )

    assert binary_hypothesis_information_gain(0.5, forecast) == pytest.approx(0.0)


def test_portfolio_penalizes_same_lineage(proposal: ExperimentProposal, clone_proposal) -> None:
    same = clone_proposal(proposal, id="EXP-002", novelty_score=0.88)
    different = clone_proposal(proposal, id="EXP-003", lineage="representation", novelty_score=0.82)
    context = GateContext(
        hypothesis_ids=frozenset({"H-001"}),
        budget=Budget(),
        usage=BudgetUsage(),
        holdout_policy="strict_blind",  # type: ignore[arg-type]
    )
    scored = evaluate_candidates([proposal, same, different], context, WEIGHTS)
    selected = select_portfolio(scored, 2, similarity_penalty=0.5)
    assert {item.proposal.id for item in selected} == {"EXP-001", "EXP-003"}


def test_a_large_metric_scale_does_not_make_the_phase_weights_decorative(proposal, clone_proposal) -> None:
    """The four utility components have to be commensurable, or the weights stop meaning anything.

    Three of them are rubric scores in [0, 1]. The expected gain was left in the competition's own
    units, so on ROC AUC (gains ~0.01) the terms stayed comparable by accident and on RMSE in feet
    they did not: the first real ROGII round scored a baseline measurement at pragmatic 11336
    against rubric scores below 1, and `epistemic: 0.45` -- the weight that makes a discovery phase
    a discovery phase -- moved the total by less than one part in five thousand.
    """
    from epistemic_loop.domain.models import EpistemicAssessment, ScoreEstimate

    def _rubric(value: int) -> EpistemicAssessment:
        return EpistemicAssessment(
            hypothesis_discrimination=value,
            uncertainty_reduction=value,
            decision_consequence=value,
            search_space_reduction=value,
            outcome_observability=value,
            rationale="fixture",
        )

    discovery = PhaseWeights(pragmatic=0.20, epistemic=0.45, robustness=0.20, diversity=0.15)
    big_gain_dull = clone_proposal(
        proposal,
        id="EXP-BASELINE",
        expected_score_gain=ScoreEstimate(mean_gain=11336.0).model_dump(),
        epistemic_assessment=_rubric(1),
    )
    no_gain_informative = clone_proposal(
        proposal,
        id="EXP-DIAGNOSTIC",
        protocol="a different protocol so this is not a duplicate",
        expected_score_gain=ScoreEstimate(mean_gain=0.0).model_dump(),
        epistemic_assessment=_rubric(4),
    )

    scored = evaluate_candidates([big_gain_dull, no_gain_informative], _context(), discovery)
    utilities = {item.proposal.id: item.utility for item in scored}

    assert utilities["EXP-BASELINE"].pragmatic_raw == 11336.0, "the record keeps the unscaled forecast"
    assert -1.0 <= utilities["EXP-BASELINE"].pragmatic <= 1.0
    assert -1.0 <= utilities["EXP-DIAGNOSTIC"].pragmatic <= 1.0
    # The decisive check: in discovery, a maximally informative experiment must be able to beat an
    # uninformative one, whatever the metric is measured in.
    assert utilities["EXP-DIAGNOSTIC"].total > utilities["EXP-BASELINE"].total

    # And the weights must actually be what moves it: swap to exploitation, where pragmatic is
    # weighted highest and epistemic lowest, and the ordering has to reverse.
    exploitation = PhaseWeights(pragmatic=0.55, epistemic=0.15, robustness=0.25, diversity=0.05)
    swapped = {
        item.proposal.id: item.utility
        for item in evaluate_candidates([big_gain_dull, no_gain_informative], _context(), exploitation)
    }
    assert swapped["EXP-BASELINE"].total > swapped["EXP-DIAGNOSTIC"].total


def test_a_forecast_of_no_gain_scores_no_gain_whatever_it_is_compared_against(proposal, clone_proposal) -> None:
    """Min-max would spend the whole range on whatever spread is present, so a diagnostic honestly
    forecasting nothing lands on 0 or 1 depending only on its neighbours. Scaling by the largest
    magnitude keeps the ratios instead."""
    from epistemic_loop.domain.models import ScoreEstimate

    def _pair(first: float, second: float) -> dict[str, float]:
        candidates = [
            clone_proposal(proposal, id="A", expected_score_gain=ScoreEstimate(mean_gain=first).model_dump()),
            clone_proposal(
                proposal,
                id="B",
                protocol="a different protocol so this is not a duplicate",
                expected_score_gain=ScoreEstimate(mean_gain=second).model_dump(),
            ),
        ]
        return {
            item.proposal.id: item.utility.pragmatic
            for item in evaluate_candidates(candidates, _context(), WEIGHTS)
        }

    assert _pair(10.0, 0.0)["B"] == 0.0, "no forecast gain is no pragmatic score"
    assert _pair(0.2, 0.1)["B"] == pytest.approx(0.5), "half the gain is half the score, not zero"
    assert _pair(5.0, 5.0) == {"A": 1.0, "B": 1.0}, "equal forecasts score equally"
    assert _pair(0.0, 0.0) == {"A": 0.0, "B": 0.0}, "nothing to scale against is not a division"
    assert _pair(10.0, -5.0)["B"] == pytest.approx(-0.5), "a candidate expecting to cost score keeps its sign"
