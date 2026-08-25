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


def test_a_command_the_executor_would_refuse_is_refused_at_the_gate(proposal: ExperimentProposal) -> None:
    """The executor's allowlist used to live only in the executor.

    A proposal starting `mkdir -p ... && python -c ...` was selected, dispatched, and raised a
    PermissionError that took the entire unattended loop down -- for a constraint the proposal could
    have been checked against before anything was committed to.
    """
    allowlist = ("python", "python3", "uv", "bash")
    shell_chain = proposal.model_copy(update={"implementation_request": {"command": "mkdir -p out && python3 run.py"}})
    result = hard_gate(shell_chain, context(command_allowlist=allowlist))
    assert not result.passed
    assert any("must start with one of" in reason and "mkdir" in reason for reason in result.reasons)

    wrapped = proposal.model_copy(update={"implementation_request": {"command": "bash -c 'mkdir out && python3 x.py'"}})
    assert hard_gate(wrapped, context(command_allowlist=allowlist)).passed, "bash is allowlisted; wrap in it"

    absolute = proposal.model_copy(update={"implementation_request": {"command": "/usr/bin/python3 run.py"}})
    assert hard_gate(absolute, context(command_allowlist=allowlist)).passed, "match on the basename"

    unparseable = proposal.model_copy(update={"implementation_request": {"command": "python3 'unclosed"}})
    assert any("could not be parsed" in r for r in hard_gate(unparseable, context(command_allowlist=allowlist)).reasons)


def test_no_allowlist_means_the_executor_imposes_none(proposal: ExperimentProposal) -> None:
    """An executor that directs a repository has no shell to protect."""
    anything = proposal.model_copy(update={"implementation_request": {"command": "make all"}})
    assert hard_gate(anything, context()).passed


def test_a_required_artifact_that_is_not_a_file_name_is_refused(proposal: ExperimentProposal) -> None:
    """These are checked for existence after the run, so a sentence is a guaranteed failure.

    An unattended designer listed "adversarial_roc_auc mean and per-seed values in metrics.json" as
    a required artifact. It cannot exist, and the round was already spent by the time anyone looked.
    """
    prose = proposal.model_copy(update={"required_artifacts": ["metrics.json", "per-seed values in metrics.json"]})
    result = hard_gate(prose, context())
    assert not result.passed
    assert any("plain relative file names" in reason for reason in result.reasons)

    absolute = proposal.model_copy(update={"required_artifacts": ["/tmp/metrics.json"]})
    assert not hard_gate(absolute, context()).passed

    fine = proposal.model_copy(update={"required_artifacts": ["metrics.json", "seed_metrics.json"]})
    assert hard_gate(fine, context()).passed
