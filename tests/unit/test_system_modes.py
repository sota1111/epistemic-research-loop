from pathlib import Path

import pytest

from epistemic_loop.config import PhaseWeights, load_config
from epistemic_loop.controller.allocation import adaptive_allocation
from epistemic_loop.domain.enums import ExperimentType, RunMode
from epistemic_loop.domain.models import Budget, BudgetUsage, CandidateDescriptors, EVSIProxy, ExperimentProposal
from epistemic_loop.domain.validation import GateContext, hard_gate
from epistemic_loop.scoring.selector import score_experiment

WEIGHTS = PhaseWeights(pragmatic=0.2, epistemic=0.45, robustness=0.2, diversity=0.15)


def test_evsi_is_computed_from_decision_change_inputs(proposal: ExperimentProposal) -> None:
    candidate = proposal.model_copy(
        update={
            "evsi_proxy": EVSIProxy(
                decision_change_probability=0.4,
                utility_difference=0.5,
                decision_ids=["primary_validation"],
                rationale="the result selects random or time CV",
            )
        }
    )
    score = score_experiment(candidate, WEIGHTS, mode=RunMode.SYSTEM_C)
    assert score.evsi == pytest.approx(0.2)
    assert score.epistemic == pytest.approx(0.2)
    assert score.epistemic_method == "evsi_proxy"


def test_system_b_cannot_accidentally_use_eig_or_evsi(proposal: ExperimentProposal) -> None:
    score = score_experiment(proposal, WEIGHTS, mode=RunMode.SYSTEM_B)
    assert score.eig == 0
    assert score.evsi == 0
    assert score.epistemic == 0
    assert score.epistemic_method == "disabled_by_system_mode"


def test_failure_probability_is_a_separate_risk_penalty(proposal: ExperimentProposal) -> None:
    risky = proposal.model_copy(
        update={"estimated_cost": proposal.estimated_cost.model_copy(update={"failure_probability": 0.6})}
    )
    safe_score = score_experiment(proposal, WEIGHTS, mode=RunMode.SYSTEM_C)
    risky_score = score_experiment(risky, WEIGHTS, mode=RunMode.SYSTEM_C)
    assert risky_score.cost == safe_score.cost
    assert risky_score.risk == pytest.approx(0.6)
    assert risky_score.total == pytest.approx(safe_score.total - 0.3)


def test_all_four_system_modes_are_config_selectable() -> None:
    root = Path(__file__).resolve().parents[2]
    expected = {
        "system_a.yaml": RunMode.SYSTEM_A,
        "system_b.yaml": RunMode.SYSTEM_B,
        "system_b_plus.yaml": RunMode.SYSTEM_B_PLUS,
        "system_c.yaml": RunMode.SYSTEM_C,
    }
    assert {name: load_config(root / "configs" / name).run.mode for name in expected} == expected


def test_explicit_system_c_cannot_bypass_likelihood_preregistration(proposal: ExperimentProposal) -> None:
    context = GateContext(
        hypothesis_ids=frozenset({"H-001"}),
        budget=Budget(),
        usage=BudgetUsage(),
        holdout_policy="strict_blind",  # type: ignore[arg-type]
        run_mode=RunMode.SYSTEM_C,
        hypotheses_with_alternatives=frozenset({"H-001"}),
    )
    result = hard_gate(proposal, context)
    assert not result.passed
    assert "System C epistemic experiments require preregistered likelihood forecasts" in result.reasons


def test_budget_allocation_respects_arm_boundaries_and_uncertainty() -> None:
    base = {"exploit": 0.3, "qd_explore": 0.3, "epistemic": 0.4}
    assert adaptive_allocation(base, mode=RunMode.SYSTEM_A) == {
        "exploit": 1.0,
        "qd_explore": 0.0,
        "epistemic": 0.0,
    }
    system_b = adaptive_allocation(base, mode=RunMode.SYSTEM_B)
    assert system_b["epistemic"] == 0
    assert system_b["qd_explore"] == pytest.approx(0.7)
    system_c = adaptive_allocation(base, mode=RunMode.SYSTEM_C, qd_occupancy=0)
    assert system_c["epistemic"] > base["epistemic"]
    assert system_c["qd_explore"] > base["qd_explore"]


def test_established_qd_population_requires_a_valid_evolutionary_parent(proposal: ExperimentProposal) -> None:
    context = GateContext(
        hypothesis_ids=frozenset({"H-001"}),
        budget=Budget(),
        usage=BudgetUsage(),
        holdout_policy="strict_blind",  # type: ignore[arg-type]
        run_mode=RunMode.SYSTEM_B,
        qd_candidate_ids=frozenset({"QD-parent"}),
    )
    seed = proposal.model_copy(
        update={"experiment_type": ExperimentType.EXPLOIT, "descriptors": CandidateDescriptors()}
    )
    invalid_parent = seed.model_copy(
        update={
            "variation_operator": "mutation",
            "parent_candidate_ids": ["QD-missing"],
        }
    )
    valid = seed.model_copy(
        update={
            "variation_operator": "mutation",
            "parent_candidate_ids": ["QD-parent"],
        }
    )

    assert any("requires mutation or crossover lineage" in reason for reason in hard_gate(seed, context).reasons)
    assert "unknown QD parent candidates: QD-missing" in hard_gate(invalid_parent, context).reasons
    assert hard_gate(valid, context).passed


def test_system_c_falsification_experiment_must_consume_independent_proposal(
    proposal: ExperimentProposal,
) -> None:
    context = GateContext(
        hypothesis_ids=frozenset({"H-001"}),
        budget=Budget(),
        usage=BudgetUsage(),
        holdout_policy="strict_blind",  # type: ignore[arg-type]
        run_mode=RunMode.SYSTEM_C,
        hypotheses_with_alternatives=frozenset({"H-001"}),
        falsification_targets={"FP-1": "H-001"},
    )
    candidate = proposal.model_copy(update={"experiment_type": ExperimentType.FALSIFICATION})

    assert any(
        "must consume an independent falsifier proposal" in reason for reason in hard_gate(candidate, context).reasons
    )
