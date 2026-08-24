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
