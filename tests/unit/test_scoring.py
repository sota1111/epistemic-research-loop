from epistemic_loop.config import PhaseWeights
from epistemic_loop.domain.models import Budget, BudgetUsage, ExperimentProposal
from epistemic_loop.domain.validation import GateContext
from epistemic_loop.scoring.selector import evaluate_candidates, score_experiment, select_portfolio

WEIGHTS = PhaseWeights(pragmatic=0.2, epistemic=0.45, robustness=0.2, diversity=0.15)


def test_utility_uses_epistemic_value(proposal: ExperimentProposal) -> None:
    score = score_experiment(proposal, WEIGHTS)
    assert score.epistemic == 0.95
    assert score.total > 0


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
