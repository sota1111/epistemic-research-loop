from epistemic_loop.domain.enums import ExperimentType, HoldoutAccess, HoldoutPolicyName
from epistemic_loop.domain.models import Budget, BudgetUsage, ExperimentProposal
from epistemic_loop.domain.validation import GateContext, experiment_fingerprint, hard_gate


def context(**changes: object) -> GateContext:
    values = {
        "hypothesis_ids": frozenset({"H-001"}),
        "budget": Budget(),
        "usage": BudgetUsage(),
        "holdout_policy": HoldoutPolicyName.STRICT_BLIND,
    }
    values.update(changes)
    return GateContext(**values)  # type: ignore[arg-type]


def test_valid_preregistration_passes(proposal: ExperimentProposal) -> None:
    assert hard_gate(proposal, context()).passed


def test_strict_holdout_is_always_rejected(proposal: ExperimentProposal) -> None:
    experiment = proposal.model_copy(update={"holdout_access": HoldoutAccess.SEALED_HOLDOUT})
    result = hard_gate(experiment, context())
    assert not result.passed
    assert any("strict_blind" in reason for reason in result.reasons)


def test_duplicate_requires_explicit_replication(proposal: ExperimentProposal) -> None:
    fingerprint = experiment_fingerprint(proposal)
    assert not hard_gate(proposal, context(prior_fingerprints=frozenset({fingerprint}))).passed
    replication = proposal.model_copy(update={"experiment_type": ExperimentType.REPLICATION})
    assert hard_gate(replication, context(prior_fingerprints=frozenset({fingerprint}))).passed


def test_fourth_optimization_is_forced_out(proposal: ExperimentProposal) -> None:
    optimization = proposal.model_copy(update={"experiment_type": ExperimentType.OPTIMIZATION})
    recent = (ExperimentType.OPTIMIZATION,) * 3
    result = hard_gate(optimization, context(recent_experiment_types=recent))
    assert not result.passed
    assert any("3 consecutive" in reason for reason in result.reasons)


def test_the_consecutive_optimization_limit_is_configurable(proposal: ExperimentProposal) -> None:
    """`max_consecutive_optimization_experiments` was a documented knob the gate never read.

    An exploiter-only control arm has to be allowed to be an exploiter, or the comparison it exists
    to provide cannot be run at all -- so 0 disables the rule, and any other value sets the run.
    """
    optimization = proposal.model_copy(update={"experiment_type": ExperimentType.OPTIMIZATION})
    recent = (ExperimentType.OPTIMIZATION,) * 5

    assert hard_gate(optimization, context(recent_experiment_types=recent, max_consecutive_optimization=0)).passed

    stricter = hard_gate(optimization, context(recent_experiment_types=recent, max_consecutive_optimization=2))
    assert not stricter.passed
    assert any("2 consecutive" in reason for reason in stricter.reasons)


def test_an_unusable_implementation_request_is_refused_before_selection(proposal: ExperimentProposal) -> None:
    """The contract is built after selection, so a bad value there costs the whole round.

    `implementation_request` is free-form by design -- different executors need different keys -- and
    every constraint on it used to live in code the proposer never sees. A model that guessed
    `network_policy: "offline"` had its experiment selected and then crashed the dispatch.
    """
    bad_policy = proposal.model_copy(
        update={"implementation_request": {"command": "python3 run.py", "network_policy": "offline"}}
    )
    result = hard_gate(bad_policy, context())
    assert not result.passed
    assert any("network_policy" in reason and "offline" in reason for reason in result.reasons)

    bad_resources = proposal.model_copy(
        update={"implementation_request": {"command": "python3 run.py", "resources": "lots"}}
    )
    assert any("resources must be an object" in reason for reason in hard_gate(bad_resources, context()).reasons)

    good = proposal.model_copy(
        update={"implementation_request": {"command": "python3 run.py", "network_policy": "disabled"}}
    )
    assert hard_gate(good, context()).passed


def test_a_brief_satisfies_the_gate_where_a_command_would(proposal: ExperimentProposal) -> None:
    """An executor that directs a repository has no command to run; it hands over a task."""
    brief_only = proposal.model_copy(
        update={"implementation_request": {"brief": {"title": "t", "objective": "o", "approach": "a"}}}
    )
    assert hard_gate(brief_only, context()).passed

    neither = proposal.model_copy(update={"implementation_request": {"objective": "just a sentence"}})
    result = hard_gate(neither, context())
    assert not result.passed
    assert any("reproducible `command` or a `brief`" in reason for reason in result.reasons)
