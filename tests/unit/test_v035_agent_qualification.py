from __future__ import annotations

import pytest

from epistemic_loop.controller.agent_qualification import (
    ActionType,
    CandidateResearchOutcome,
    CycleProposalSet,
    LocalCandidateStatus,
    LocalResearchPortfolio,
    LocalSearchStagnationDetector,
    ModeUpdateEvidence,
    ResearchDescriptor,
    ResearchMode,
    ResearchProposal,
    build_population_scorecard,
)


def _proposal(agent: str, cycle: int, mode: ResearchMode, family: str) -> ResearchProposal:
    return ResearchProposal(
        proposal_id=f"{agent}-{cycle}-{mode.value}",
        agent_id=agent,
        cycle=cycle,
        mode=mode,
        purpose=f"investigate {family}",
        descriptor=ResearchDescriptor(
            hypothesis_family=family,
            representation_family=f"repr-{family}",
            validation_world="strict-forward",
            data_slice=f"slice-{family}",
            experiment_operator=f"operator-{family}",
            model_family="generic-model",
            downstream_decision=f"decision-{family}",
            structural_claim=mode is ResearchMode.EPISTEMIC,
        ),
    )


def _proposal_set(agent: str, cycle: int, selected_family: str) -> CycleProposalSet:
    return CycleProposalSet(
        agent,
        cycle,
        (
            _proposal(agent, cycle, ResearchMode.EXPLOIT, f"incumbent-{cycle}"),
            _proposal(agent, cycle, ResearchMode.EXPLORE, selected_family),
            _proposal(agent, cycle, ResearchMode.EPISTEMIC, f"uncertainty-{cycle}"),
        ),
    )


def _outcome(
    proposal: ResearchProposal,
    *,
    status: LocalCandidateStatus = LocalCandidateStatus.REJECTED,
    improvement: bool = False,
    uncertainty: float = 0.4,
    challenger_sealed: float = 0.82,
    parent_sealed: float = 0.80,
) -> CandidateResearchOutcome:
    return CandidateResearchOutcome(
        proposal=proposal,
        candidate_id=f"candidate-{proposal.proposal_id}",
        action_type=(
            ActionType.EPISTEMIC_EXPLORATION
            if proposal.mode is ResearchMode.EPISTEMIC
            else ActionType.SOLUTION_EXPLORATION
        ),
        local_status=status,
        local_primary_metric=0.81,
        artifact_valid=True,
        leakage_safe=True,
        predictions_available=True,
        selected_as_next_parent=status is LocalCandidateStatus.ACCEPTED,
        decision_changed=status is LocalCandidateStatus.ACCEPTED,
        candidate_improved=improvement,
        uncertainty_reduction=uncertainty,
        ensemble_potential=0.2,
        structural_leverage=2.0 if proposal.descriptor.structural_claim else 0.0,
        structure_validation_strength=0.5,
        parent_semantic_distance=0.5,
        sealed_primary_metric=challenger_sealed,
        sealed_parent_metric=parent_sealed,
    )


def test_cycle_requires_local_exploit_explore_and_epistemic_proposals() -> None:
    valid = _proposal_set("agent-01", 1, "entity")
    assert len(valid.proposals) == 3
    with pytest.raises(ValueError, match="at least three"):
        CycleProposalSet("agent-01", 1, valid.proposals[:2])


def test_shadow_archive_retains_a_false_rejection_and_elites_are_separate() -> None:
    portfolio = LocalResearchPortfolio("agent-01")
    proposals = _proposal_set("agent-01", 1, "entity")
    portfolio.register_proposals(proposals)
    rejected = _outcome(proposals.proposals[1])
    portfolio.record(rejected)

    assert portfolio.shadow_candidates == (rejected,)
    assert portfolio.final_recheck_candidates == (rejected,)
    assert rejected.sealed_decision_regret == pytest.approx(0.02)
    assert portfolio.elites.performance == rejected
    assert portfolio.elites.information == rejected


def test_mode_allocation_and_stagnation_are_agent_local() -> None:
    portfolio = LocalResearchPortfolio("agent-01")
    updated = portfolio.update_mode_allocation(
        ModeUpdateEvidence(new_research_state_coverage=1.0, candidate_complementarity=1.0)
    )
    assert updated.explore > updated.exploit

    detector = LocalSearchStagnationDetector()
    for cycle in (1, 2):
        proposals = _proposal_set("agent-01", cycle, "same-family")
        portfolio.register_proposals(proposals)
        decision = detector.assess(
            _outcome(proposals.proposals[1], uncertainty=0.0, challenger_sealed=0.8, parent_sealed=0.8)
        )
    assert decision.stagnated
    assert decision.notification is not None
    assert "異なる説明" in decision.notification


def test_population_scorecard_is_observe_only_and_recovers_shadow_candidates() -> None:
    portfolios: list[LocalResearchPortfolio] = []
    families = (
        ("validation", "entity", "capacity"),
        ("time", "behavior", "learner"),
        ("recurrence", "amount", "missingness"),
    )
    action_types = (
        ActionType.EPISTEMIC_EXPLORATION,
        ActionType.STRUCTURE_MATURATION,
        ActionType.EXPLOITATION,
    )
    for agent_index, agent_families in enumerate(families, start=1):
        agent = f"agent-{agent_index:02d}"
        portfolio = LocalResearchPortfolio(agent)
        for cycle, (family, action) in enumerate(zip(agent_families, action_types, strict=True), start=1):
            proposals = _proposal_set(agent, cycle, family)
            portfolio.register_proposals(proposals)
            proposal = proposals.proposals[1]
            outcome = _outcome(proposal)
            portfolio.record(
                CandidateResearchOutcome(
                    **{
                        **outcome.__dict__,
                        "action_type": action,
                        "candidate_improved": cycle == 3,
                    }
                )
            )
        portfolios.append(portfolio)

    report = build_population_scorecard(portfolios)
    assert report.qualifying_agents == 3
    assert report.population_effective_research_family >= 2.5
    assert report.diversity_gate_passed
    assert report.action_balance_gate_passed
    assert report.shadow_candidate_recovery_rate == 1.0
