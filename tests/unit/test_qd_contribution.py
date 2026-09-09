"""Novelty is measured against the archive, not declared by the proposer (§3 item 11).

`docs/v050_course_correction.md` §2.2: the campaign said it was running System B and ran an argmax
on score. B's utility is supposed to carry novelty / QD contribution, and what it carried was a
number the proposer wrote about itself.
"""

from __future__ import annotations

from typing import Any

import pytest

from epistemic_loop.config import PhaseWeights
from epistemic_loop.domain.enums import RunMode
from epistemic_loop.domain.models import CandidateDescriptors, ExperimentProposal, QDCandidate
from epistemic_loop.qd.descriptors import SOLUTION_DESCRIPTORS
from epistemic_loop.scoring.qd_contribution import CELL_SLOTS, cell_census, qd_contribution
from epistemic_loop.scoring.selector import score_experiment

WEIGHTS = PhaseWeights(pragmatic=0.2, epistemic=0.2, robustness=0.2, diversity=0.4)


def _descriptors(**overrides: Any) -> CandidateDescriptors:
    payload: dict[str, Any] = {
        "model_family": "gbdt",
        "representation": "tabular",
        "data_scope": "full",
        "validation_type": "time",
        "shift_hypothesis": "none",
        "entity_hypothesis": "none",
        "error_profile": "balanced",
    }
    payload.update(overrides)
    return CandidateDescriptors(**payload)


def _candidate(identifier: str, **overrides: Any) -> QDCandidate:
    return QDCandidate(
        id=identifier,
        run_id="RUN-001",
        experiment_id=f"EXP-{identifier}",
        descriptors=_descriptors(**overrides),
        expected_hidden_score=0.8,
        score_variance=0.01,
        normalized_cost=0.1,
        leakage_risk=0.0,
    )


def _proposal(proposal: ExperimentProposal, **overrides: Any) -> ExperimentProposal:
    return proposal.model_copy(update=overrides)


def test_an_empty_cell_is_worth_the_whole_term_and_a_full_one_nothing(proposal: ExperimentProposal) -> None:
    census = cell_census([_candidate(f"c{index}") for index in range(CELL_SLOTS)], SOLUTION_DESCRIPTORS)
    crowded = _proposal(proposal, descriptors=_descriptors())
    fresh = _proposal(proposal, descriptors=_descriptors(model_family="linear"))

    assert qd_contribution(crowded, census, SOLUTION_DESCRIPTORS) == 0.0
    assert qd_contribution(fresh, census, SOLUTION_DESCRIPTORS) == 1.0


def test_contribution_decreases_as_the_cell_fills(proposal: ExperimentProposal) -> None:
    candidate = _proposal(proposal, descriptors=_descriptors())

    values = [
        qd_contribution(
            candidate,
            cell_census([_candidate(f"c{i}") for i in range(count)], SOLUTION_DESCRIPTORS),
            SOLUTION_DESCRIPTORS,
        )
        for count in range(CELL_SLOTS + 1)
    ]

    assert values == [1.0, 0.75, 0.5, 0.25, 0.0]


def test_a_proposal_with_no_declared_descriptors_cannot_be_measured(proposal: ExperimentProposal) -> None:
    """Novelty you did not specify in advance is novelty you cannot be held to."""
    assert qd_contribution(_proposal(proposal, descriptors=None), {}, SOLUTION_DESCRIPTORS) is None


def test_the_selector_prefers_the_measurement_and_records_which_it_used(proposal: ExperimentProposal) -> None:
    census = cell_census([_candidate(f"c{index}") for index in range(CELL_SLOTS)], SOLUTION_DESCRIPTORS)
    # The proposer claims maximum novelty for work that lands in an already-full cell.
    boastful = _proposal(proposal, novelty_score=1.0, descriptors=_descriptors())

    measured = score_experiment(
        boastful,
        WEIGHTS,
        mode=RunMode.SYSTEM_B,
        qd_census=census,
        qd_descriptor_names=SOLUTION_DESCRIPTORS,
    )
    declared = score_experiment(boastful, WEIGHTS, mode=RunMode.SYSTEM_B)

    assert measured.diversity == 0.0
    assert measured.diversity_method == "qd_contribution_v1"
    assert declared.diversity == 1.0
    assert declared.diversity_method == "declared_novelty_v1"
    assert measured.total < declared.total


def test_the_declared_score_is_still_used_when_the_proposal_says_nothing(proposal: ExperimentProposal) -> None:
    undeclared = _proposal(proposal, novelty_score=0.7, descriptors=None)

    utility = score_experiment(
        undeclared,
        WEIGHTS,
        mode=RunMode.SYSTEM_B,
        qd_census={},
        qd_descriptor_names=SOLUTION_DESCRIPTORS,
    )

    assert utility.diversity == pytest.approx(0.7)
    assert utility.diversity_method == "declared_novelty_v1"


def test_system_a_has_no_diversity_term_at_all(proposal: ExperimentProposal) -> None:
    utility = score_experiment(
        _proposal(proposal, novelty_score=1.0, descriptors=_descriptors()),
        WEIGHTS,
        mode=RunMode.SYSTEM_A,
        qd_census={},
        qd_descriptor_names=SOLUTION_DESCRIPTORS,
    )

    assert utility.diversity == 0.0
    assert utility.diversity_method == "disabled_by_system_mode"
