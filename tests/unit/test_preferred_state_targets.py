"""Absent preferred-state targets are missing, not zero (§3 item 8).

`docs/v050_course_correction.md` §1.2: seven hand-written constants stood in for a world model,
and six of the specification's thirteen states were covered by them while seven had no
representation at all. Nothing in the code said so. A gap of zero against a state that was never
measured reads exactly like a state in perfect health.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from epistemic_loop.config import PreferredStateConfig
from epistemic_loop.controller.research_state import derive_research_state
from epistemic_loop.controller.run_state import RunState
from epistemic_loop.domain.enums import LoopState, Phase, RunMode
from epistemic_loop.domain.models import BudgetUsage, ResearchRun
from epistemic_loop.domain.preferred_state import (
    CORPUS_BLIND_STATES,
    MEASURED_DIMENSIONS,
    SPECIFICATION_STATES,
    UNMEASURED_STATES,
)


def _state() -> RunState:
    run = ResearchRun(
        id="RUN-001",
        competition_id="demo",
        mode=RunMode.SYSTEM_C,
        seed=1,
        base_commit_sha="0" * 40,
        dataset_fingerprint="d" * 64,
        config_hash="0" * 64,
        primary_metric="roc_auc",
    )
    return RunState(
        run=run,
        loop_state=LoopState.PLANNING,
        phase=Phase.DISCOVERY,
        hypotheses={},
        proposals={},
        experiment_statuses={},
        observations={},
        falsifications={},
        usage=BudgetUsage(),
        selection_order=(),
        violations=0,
    )


def test_no_targets_reports_every_dimension_missing_and_no_total_gap() -> None:
    snapshot = derive_research_state(_state())

    assert snapshot.preferred_state_gaps == {}
    assert snapshot.preferred_state_total_gap is None  # not 0.0: nothing was asked for
    assert set(snapshot.preferred_state_missing) == set(MEASURED_DIMENSIONS)


def test_supplied_targets_produce_gaps_and_shrink_the_missing_list() -> None:
    snapshot = derive_research_state(_state(), preferred_targets={"robustness": 0.8})

    assert snapshot.preferred_state_gaps == {"robustness": 0.8}
    assert snapshot.preferred_state_total_gap == pytest.approx(0.8)
    assert "robustness" not in snapshot.preferred_state_missing
    assert "validation_fidelity" in snapshot.preferred_state_missing


def test_a_target_for_a_dimension_the_loop_cannot_compute_is_refused() -> None:
    """The seven specification states with no measured dimension cannot be quietly targeted."""
    with pytest.raises(ValueError, match="cannot compute"):
        derive_research_state(_state(), preferred_targets={"entity_temporal_integrity": 0.5})


def test_the_snapshot_names_the_states_it_does_not_measure_at_all() -> None:
    snapshot = derive_research_state(_state())

    assert len(SPECIFICATION_STATES) == 13
    assert len(UNMEASURED_STATES) == 7
    assert snapshot.unmeasured_states == [SPECIFICATION_STATES[key] for key in UNMEASURED_STATES]
    # The two the winner corpus can never supply (docs/world_model/results.md 2.4). FC has a
    # measured dimension but no prior; HCAL has neither.
    assert set(CORPUS_BLIND_STATES) == {"HCAL", "FC"}
    assert "Hypothesis Calibration" in snapshot.unmeasured_states


def test_the_config_default_carries_no_targets() -> None:
    assert PreferredStateConfig().targets == {}


def test_setting_a_target_requires_naming_where_the_number_came_from() -> None:
    with pytest.raises(ValidationError, match="source"):
        PreferredStateConfig(targets={"robustness": 0.8})

    cited = PreferredStateConfig(targets={"robustness": 0.8}, source="docs/world_model/world_model.json rev 2")
    assert cited.targets == {"robustness": 0.8}


def test_the_config_refuses_unknown_dimensions() -> None:
    with pytest.raises(ValidationError, match="unknown preferred-state dimension"):
        PreferredStateConfig(targets={"vibes": 0.8}, source="nowhere")
