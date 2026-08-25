from __future__ import annotations

from epistemic_loop.domain.enums import ExperimentType, HoldoutPolicyName
from epistemic_loop.domain.models import Budget, BudgetUsage, ExperimentProposal
from epistemic_loop.domain.validation import GateContext, hard_gate
from epistemic_loop.holdout.adaptivity import (
    consumes_adaptivity,
    exhausted,
    validation_fingerprint,
    validation_reuse,
)


def _context(reuse: dict[str, int], budget: int) -> GateContext:
    return GateContext(
        hypothesis_ids=frozenset({"H-001"}),
        budget=Budget(),
        usage=BudgetUsage(),
        holdout_policy=HoldoutPolicyName.STRICT_BLIND,
        validation_reuse=reuse,
        max_validation_reuse=budget,
    )


def test_the_same_split_and_metric_are_one_validation_scheme(
    proposal: ExperimentProposal,
    clone_proposal,
) -> None:
    """Two different models scored on one split are two queries to the same validation set."""
    other_model = clone_proposal(proposal, id="EXP-002", protocol="train a different model family")
    assert validation_fingerprint(proposal) == validation_fingerprint(other_model)

    rotated = clone_proposal(proposal, id="EXP-003", split_strategy="grouped_by_entity")
    assert validation_fingerprint(rotated) != validation_fingerprint(proposal)


def test_whitespace_and_case_do_not_create_a_fresh_validation_scheme(
    proposal: ExperimentProposal,
    clone_proposal,
) -> None:
    restyled = clone_proposal(proposal, id="EXP-002", split_strategy="  Random_Vs_Temporal  ")
    assert validation_fingerprint(restyled) == validation_fingerprint(proposal)


def test_only_selecting_experiments_spend_the_budget(
    proposal: ExperimentProposal,
    clone_proposal,
) -> None:
    optimization = clone_proposal(proposal, id="EXP-OPT", experiment_type=ExperimentType.OPTIMIZATION)
    assert consumes_adaptivity(optimization) is True
    for kind in (
        ExperimentType.DIAGNOSTIC,
        ExperimentType.FALSIFICATION,
        ExperimentType.REPLICATION,
        ExperimentType.ROBUSTNESS,
    ):
        assert consumes_adaptivity(clone_proposal(proposal, id=f"EXP-{kind}", experiment_type=kind)) is False


def test_reuse_counts_only_experiments_the_run_committed_to(
    proposal: ExperimentProposal,
    clone_proposal,
) -> None:
    """A proposal that was scored and never run never saw the split, so it cannot have overfitted it."""
    ran = clone_proposal(proposal, id="EXP-RAN", experiment_type=ExperimentType.OPTIMIZATION)
    never_ran = clone_proposal(proposal, id="EXP-SHELVED", experiment_type=ExperimentType.OPTIMIZATION)
    counts = validation_reuse({ran.id: ran, never_ran.id: never_ran}, frozenset({"EXP-RAN"}))
    assert counts == {validation_fingerprint(ran): 1}


def test_an_exhausted_budget_blocks_another_optimization_run_on_that_split(
    proposal: ExperimentProposal,
    clone_proposal,
) -> None:
    optimization = clone_proposal(proposal, id="EXP-OPT", experiment_type=ExperimentType.OPTIMIZATION)
    spent = {validation_fingerprint(optimization): 8}

    assert exhausted(optimization, spent, budget=8) is True
    result = hard_gate(optimization, _context(spent, budget=8))
    assert not result.passed
    assert any("validation adaptivity budget" in reason for reason in result.reasons)


def test_the_budget_is_escaped_by_rotating_the_split_or_running_a_diagnostic(
    proposal: ExperimentProposal,
    clone_proposal,
) -> None:
    optimization = clone_proposal(proposal, id="EXP-OPT", experiment_type=ExperimentType.OPTIMIZATION)
    spent = {validation_fingerprint(optimization): 8}

    rotated = clone_proposal(optimization, id="EXP-ROT", split_strategy="grouped_by_entity")
    assert hard_gate(rotated, _context(spent, budget=8)).passed

    diagnostic = clone_proposal(optimization, id="EXP-DIAG", experiment_type=ExperimentType.DIAGNOSTIC)
    assert hard_gate(diagnostic, _context(spent, budget=8)).passed


def test_a_zero_budget_disables_the_guard(proposal: ExperimentProposal, clone_proposal) -> None:
    optimization = clone_proposal(proposal, id="EXP-OPT", experiment_type=ExperimentType.OPTIMIZATION)
    spent = {validation_fingerprint(optimization): 99}
    assert exhausted(optimization, spent, budget=0) is False
    assert hard_gate(optimization, _context(spent, budget=0)).passed


def test_the_research_brief_constrains_what_exploitation_may_run(proposal, clone_proposal) -> None:
    """A brief the exploiter can ignore is a record of a decision, not a hand-off.

    Publishing one is what opens exploitation, so once it exists the search space it names is the
    search space. An experiment outside it is proposing to explore, which is exactly what the
    hand-off ended.
    """
    from epistemic_loop.domain.enums import HoldoutAccess

    inside = clone_proposal(proposal, id="EXP-IN", lineage="gbdt")
    outside = clone_proposal(proposal, id="EXP-OUT", lineage="a-lineage-the-brief-never-approved")
    context = GateContext(
        hypothesis_ids=frozenset({"H-001"}),
        budget=Budget(),
        usage=BudgetUsage(),
        holdout_policy=HoldoutPolicyName.GATED_BINARY,
        approved_lineages=frozenset({"gbdt", "ensemble"}),
        prohibited_shortcuts=("sealed holdout optimization", "public leaderboard feedback"),
    )

    assert hard_gate(inside, context).passed
    refused = hard_gate(outside, context)
    assert not refused.passed
    assert any("outside the research brief" in reason for reason in refused.reasons)

    shortcut = clone_proposal(inside, id="EXP-PEEK", holdout_access=HoldoutAccess.SEALED_HOLDOUT)
    blocked = hard_gate(shortcut, context)
    assert not blocked.passed
    assert any("prohibits sealed holdout" in reason for reason in blocked.reasons)


def test_no_brief_means_no_lineage_restriction(proposal, clone_proposal) -> None:
    """Discovery has no approved set yet, and constraining it to one would defeat the point."""
    anything = clone_proposal(proposal, id="EXP-NEW", lineage="a-lineage-nobody-has-tried")
    context = GateContext(
        hypothesis_ids=frozenset({"H-001"}),
        budget=Budget(),
        usage=BudgetUsage(),
        holdout_policy=HoldoutPolicyName.STRICT_BLIND,
    )
    assert hard_gate(anything, context).passed
