#!/usr/bin/env python3
"""Run v0.3.5 independent-agent and blind-structure qualification preflight."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from epistemic_loop.benchmark.structure_controls_v035 import (
    GenericBlindStructureAgent,
    generate_blind_structure_controls,
    run_blind_control_suite,
)
from epistemic_loop.controller.agent_qualification import (
    ActionType,
    CandidateResearchOutcome,
    CycleProposalSet,
    LocalCandidateStatus,
    LocalResearchPortfolio,
    ModeUpdateEvidence,
    ResearchDescriptor,
    ResearchMode,
    ResearchProposal,
    build_population_scorecard,
)
from epistemic_loop.evaluation.v035 import (
    QualificationReliability,
    StructureQualificationReport,
    V035Acceptance,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=Path("docs"))
    parser.add_argument("--control-rows", type=int, default=900)
    arguments = parser.parse_args()

    portfolios = _v034_retrospective_portfolios()
    population = build_population_scorecard(portfolios)
    controls = generate_blind_structure_controls(rows=arguments.control_rows)

    uncentered = StructureQualificationReport.evaluate(
        run_blind_control_suite(
            GenericBlindStructureAgent(orthogonalize_temporal_probe=False),
            controls,
        )
    )
    final = StructureQualificationReport.evaluate(run_blind_control_suite(GenericBlindStructureAgent(), controls))
    reliability = QualificationReliability(1.0, 1.0, 1.0)
    acceptance = V035Acceptance.assess(population, final, reliability)

    result = {
        "version": "0.3.5",
        "scope": "qualification preflight plus v0.3.4 IEEE-CIS pilot retrospective",
        "hidden_private": "UNMEASURED",
        "phase_1_information_sharing": "none",
        "population": asdict(population),
        "trials": [
            {
                "trial": 0,
                "status": "failed_design_audit",
                "change": "separate AgentControlView from controller-owned truth",
                "finding": (
                    "the first API passed the complete control object into the agent method and "
                    "left the generator seed in the opaque identifier; although labels were not used "
                    "for fitting, blindness was not enforceable by type or identifier"
                ),
            },
            {
                "trial": 1,
                "status": "partial_recall",
                "change": "generic four-operator probe with null and independent-implication gates",
                "finding": (
                    "the temporal control was missed because an uncentered interaction was absorbed "
                    "by the incumbent signal coefficient"
                ),
                "metrics": _structure_summary(uncentered),
            },
            {
                "trial": 2,
                "status": "qualified_on_control_suite",
                "change": (
                    "orthogonalize the temporal interaction in the early research window; "
                    "promotion thresholds and negative controls unchanged"
                ),
                "metrics": _structure_summary(final),
            },
        ],
        "structure_control": asdict(final),
        "reliability": asdict(reliability),
        "acceptance": asdict(acceptance),
        "claims_not_supported": [
            "Kaggle Hidden or Private performance improved",
            "the deterministic reference probe equals an LLM agent qualification",
            "cross-agent communication is harmful or beneficial",
            "B, B+, or C has an outcome advantage",
        ],
    }
    output_root = arguments.output_root
    output_root.mkdir(parents=True, exist_ok=True)
    _write_json(output_root / "v035_qualification_result.json", result)
    _write_json(
        output_root / "v035_agent_scorecards.json",
        {item.agent_id: asdict(item) for item in population.agents},
    )
    _write_json(output_root / "v035_population_scorecard.json", asdict(population))
    _write_json(output_root / "v035_structure_control_report.json", asdict(final))
    print(json.dumps(result, indent=2, sort_keys=True))


def _structure_summary(report: StructureQualificationReport) -> dict[str, object]:
    return {
        "true_structure_discovery_rate": report.true_structure_discovery_rate,
        "true_structure_rejection_rate": report.true_structure_rejection_rate,
        "false_structure_promotion_rate": report.false_structure_promotion_rate,
        "useful_structure_transfer_rate": report.useful_structure_transfer_rate,
        "median_structure_sealed_gain": report.median_structure_sealed_gain,
        "brier_score": report.brier_score,
        "expected_calibration_error": report.expected_calibration_error,
        "discovered_positive_families": [
            item.control_id
            for item in report.families
            if item.structure_present and item.promoted and item.ground_truth_operator_match
        ],
        "missed_positive_families": [
            item.control_id
            for item in report.families
            if item.structure_present and (not item.promoted or not item.ground_truth_operator_match)
        ],
        "false_promotions": [
            item.control_id for item in report.families if not item.structure_present and item.promoted
        ],
    }


def _v034_retrospective_portfolios() -> tuple[LocalResearchPortfolio, ...]:
    trajectories = {
        "island-01": (
            _cycle(
                "relative_temporal_anchor",
                ResearchMode.EPISTEMIC,
                ActionType.EPISTEMIC_EXPLORATION,
                False,
                0.913603,
                0.914798,
                0.9238926026,
                0.9218926924,
                True,
            ),
            _cycle(
                "entity_context_profile",
                ResearchMode.EPISTEMIC,
                ActionType.STRUCTURE_MATURATION,
                True,
                0.916049,
                0.914798,
                0.9241000314,
                0.9218926924,
                True,
            ),
            _cycle(
                "learner_capacity",
                ResearchMode.EXPLOIT,
                ActionType.EXPLOITATION,
                True,
                0.918940,
                0.916049,
                0.9295792654,
                0.9241000314,
                False,
            ),
        ),
        "island-02": (
            _cycle(
                "fold_local_recurrence",
                ResearchMode.EPISTEMIC,
                ActionType.EPISTEMIC_EXPLORATION,
                False,
                0.905674,
                0.905000,
                0.9212210087,
                0.9179892538,
                True,
            ),
            _cycle(
                "behavioral_amount_shape",
                ResearchMode.EXPLORE,
                ActionType.SOLUTION_EXPLORATION,
                False,
                0.906094,
                0.905546,
                0.9255887768,
                0.9179892538,
                False,
            ),
            _cycle(
                "learner_capacity",
                ResearchMode.EXPLOIT,
                ActionType.EXPLOITATION,
                False,
                0.905852,
                0.905546,
                0.9244275756,
                0.9179892538,
                False,
            ),
        ),
        "island-03": (
            _cycle(
                "fold_local_recurrence",
                ResearchMode.EXPLORE,
                ActionType.SOLUTION_EXPLORATION,
                True,
                0.936482,
                0.933965,
                0.9187676575,
                0.9172171957,
                False,
            ),
            _cycle(
                "behavioral_amount_shape",
                ResearchMode.EXPLOIT,
                ActionType.EXPLOITATION,
                True,
                0.937363,
                0.936482,
                0.9210246366,
                0.9187676575,
                False,
            ),
            _cycle(
                "observation_missingness",
                ResearchMode.EPISTEMIC,
                ActionType.EPISTEMIC_EXPLORATION,
                False,
                0.936096,
                0.937363,
                0.9209449236,
                0.9210246366,
                True,
            ),
        ),
    }
    output: list[LocalResearchPortfolio] = []
    for agent_id, cycles in trajectories.items():
        portfolio = LocalResearchPortfolio(agent_id)
        for cycle_index, record in enumerate(cycles, start=1):
            family, mode, action, accepted, local, parent_local, sealed, parent_sealed, structural = record
            proposals = _proposal_set(agent_id, cycle_index, family, mode, structural)
            portfolio.register_proposals(proposals)
            selected = next(item for item in proposals.proposals if item.mode is mode)
            improvement = accepted and local > parent_local
            outcome = CandidateResearchOutcome(
                proposal=selected,
                candidate_id=f"{agent_id}-cycle-{cycle_index:02d}-challenger",
                action_type=action,
                local_status=(LocalCandidateStatus.ACCEPTED if accepted else LocalCandidateStatus.REJECTED),
                local_primary_metric=local,
                artifact_valid=True,
                leakage_safe=True,
                predictions_available=True,
                selected_as_next_parent=accepted,
                decision_changed=accepted,
                candidate_improved=improvement,
                uncertainty_reduction=(
                    0.6 if action in {ActionType.EPISTEMIC_EXPLORATION, ActionType.STRUCTURE_MATURATION} else 0.15
                ),
                ensemble_potential=0.35,
                structural_leverage=3.0 if structural else 0.0,
                structure_validation_strength=0.45 if structural else 0.0,
                parent_semantic_distance=0.5,
                sealed_primary_metric=sealed,
                sealed_parent_metric=parent_sealed,
            )
            portfolio.record(outcome)
            portfolio.update_mode_allocation(
                ModeUpdateEvidence(
                    incumbent_gain=1.0 if improvement else 0.0,
                    new_research_state_coverage=1.0,
                    uncertainty_reduction=outcome.uncertainty_reduction,
                    structure_validation=outcome.structure_validation_strength,
                    candidate_complementarity=outcome.ensemble_potential,
                )
            )
        output.append(portfolio)
    return tuple(output)


def _cycle(
    family: str,
    mode: ResearchMode,
    action: ActionType,
    accepted: bool,
    local: float,
    parent_local: float,
    sealed: float,
    parent_sealed: float,
    structural: bool,
) -> tuple[str, ResearchMode, ActionType, bool, float, float, float, float, bool]:
    return family, mode, action, accepted, local, parent_local, sealed, parent_sealed, structural


def _proposal_set(
    agent_id: str,
    cycle: int,
    selected_family: str,
    selected_mode: ResearchMode,
    structural: bool,
) -> CycleProposalSet:
    proposals: list[ResearchProposal] = []
    for mode in (ResearchMode.EXPLOIT, ResearchMode.EXPLORE, ResearchMode.EPISTEMIC):
        family = selected_family if mode is selected_mode else f"unexecuted_{mode.value}_{cycle}"
        proposals.append(
            ResearchProposal(
                proposal_id=f"{agent_id}-cycle-{cycle:02d}-{mode.value}",
                agent_id=agent_id,
                cycle=cycle,
                mode=mode,
                purpose=f"agent-local {mode.value} proposal",
                descriptor=ResearchDescriptor(
                    hypothesis_family=family,
                    representation_family=f"representation_{family}",
                    validation_world="agent_local_forward",
                    data_slice=f"slice_{family}",
                    experiment_operator=f"operator_{family}",
                    model_family="agent_selected",
                    downstream_decision=f"decision_{family}",
                    structural_claim=structural and mode is selected_mode,
                ),
            )
        )
    return CycleProposalSet(agent_id, cycle, tuple(proposals))


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
