import pytest

from epistemic_loop.controller.budget_manager import BudgetManager
from epistemic_loop.controller.state_machine import InvalidTransition, ResearchStateMachine
from epistemic_loop.domain.enums import LoopState
from epistemic_loop.domain.models import Budget, CostEstimate


def test_state_machine_rejects_skipping_preregistration() -> None:
    machine = ResearchStateMachine()
    with pytest.raises(InvalidTransition):
        machine.transition(LoopState.EXECUTING)


def test_budget_reservation_is_atomic() -> None:
    manager = BudgetManager(Budget(max_experiments=1, max_cpu_hours=1))
    manager.reserve(CostEstimate(cpu_hours=1))
    with pytest.raises(ValueError, match="budget exceeded"):
        manager.reserve(CostEstimate(cpu_hours=0))


def test_a_zero_resource_budget_does_not_stop_the_run() -> None:
    """A budget of zero means the run does not use that resource, not that it ran out.

    Read as exhaustion it stops every CPU-only run on its first round for having consumed no GPU,
    which is what happened the first time the unattended loop was run.
    """
    from epistemic_loop.controller.stop_policy import should_stop
    from epistemic_loop.domain.models import Budget, BudgetUsage

    cpu_only = Budget(max_cpu_hours=60, max_gpu_hours=0)
    decision = should_stop(cpu_only, BudgetUsage(), maximum_candidate_utility=1.0, minimum_utility=0.0)
    assert not decision.stop, decision.reasons

    spent = should_stop(
        Budget(max_cpu_hours=60, max_gpu_hours=4),
        BudgetUsage(gpu_hours=4),
        maximum_candidate_utility=1.0,
        minimum_utility=0.0,
    )
    assert spent.stop and "GPU budget exhausted" in spent.reasons


def test_the_schema_tells_the_proposer_what_the_gate_will_require(proposal) -> None:
    """The gate rejects a proposal with no runnable command; the schema has to say so.

    A proposer reads the JSON Schema, not the gate. Enforcing a requirement the schema never states
    is how five well-formed proposals in a row get refused for a field nobody was told about.
    """
    from epistemic_loop.domain.models import ExperimentProposal

    described = ExperimentProposal.model_json_schema()["properties"]["implementation_request"]["description"]
    assert "`command`" in described and "reproducible" in described
    assert "`brief`" in described, "the other executor's requirement must be stated too"
