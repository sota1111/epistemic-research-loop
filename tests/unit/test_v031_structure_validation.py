from __future__ import annotations

from epistemic_loop.controller.structure_validation import (
    MatchedNullSequentialFutilityRule,
    StructureTerminalEvidence,
    decide_structure_terminal_state,
)
from epistemic_loop.domain.enums import StructureClassification, StructureLifecycleState
from epistemic_loop.domain.models import StructureValidationDebt


def test_sequential_futility_stops_when_null_tail_rejection_is_implausible() -> None:
    decision = MatchedNullSequentialFutilityRule().assess(
        real_gain=0.0009,
        matched_null_gains=(0.0001, 0.0002, 0.0010, 0.0003, 0.0004),
    )
    assert decision.stop_for_futility
    assert decision.null_gains_at_least_real == 1
    assert decision.posterior_probability_null_tail_below_five_percent < 0.05


def test_structure_with_useful_auc_but_failed_null_remains_unvalidated_encoding() -> None:
    decision = decide_structure_terminal_state(
        StructureTerminalEvidence(
            null_rejected=False,
            independent_implication_reproduced=False,
            multi_context_multi_seed_reproduced=False,
            decision_improved=False,
            predictive_gain_reproduced=True,
        )
    )
    assert decision.lifecycle_state == StructureLifecycleState.USEFUL_ENCODING_UNVALIDATED_STRUCTURE
    assert decision.classification == StructureClassification.USEFUL_ENCODING_UNVALIDATED_STRUCTURE


def test_only_independent_replicated_and_adopted_structure_is_actionable() -> None:
    decision = decide_structure_terminal_state(
        StructureTerminalEvidence(
            null_rejected=True,
            independent_implication_reproduced=True,
            multi_context_multi_seed_reproduced=True,
            decision_improved=True,
            predictive_gain_reproduced=True,
        )
    )
    assert decision.lifecycle_state == StructureLifecycleState.VALIDATED_STRUCTURE
    assert decision.classification == StructureClassification.VALIDATED_ACTIONABLE_STRUCTURE


def test_legacy_debt_resolution_artifact_is_backfilled_as_passed() -> None:
    debt = StructureValidationDebt.model_validate(
        {
            "debt_id": "DEBT-1",
            "hypothesis_id": "H-1",
            "structure_type": "generic",
            "unresolved_requirements": ["null"],
            "resolution_artifacts": {"null": "artifact.json"},
            "status": "resolved",
            "owner_agent": "agent-1",
        }
    )
    assert debt.resolution_outcomes["null"].value == "passed"
