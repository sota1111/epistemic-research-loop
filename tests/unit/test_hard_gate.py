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
    assert any("three consecutive" in reason for reason in result.reasons)
