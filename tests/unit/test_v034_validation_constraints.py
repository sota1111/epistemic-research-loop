from __future__ import annotations

import pytest

from epistemic_loop.controller.validation_constraints import (
    ConstraintEvidence,
    GlobalValidationConstraintRegistry,
    ValidationArtifactDescriptor,
    ValidationGeometry,
    ValidationUse,
)


def _artifact(geometry: ValidationGeometry) -> ValidationArtifactDescriptor:
    return ValidationArtifactDescriptor("candidate", geometry, True, True, True, True)


def test_frozen_constraint_excludes_shuffled_from_future_pool_but_not_diagnostics() -> None:
    registry = GlobalValidationConstraintRegistry()

    final = registry.assess(_artifact(ValidationGeometry.SHUFFLED), ValidationUse.FINAL_CANDIDATE_POOL)
    diagnostic = registry.assess(_artifact(ValidationGeometry.SHUFFLED), ValidationUse.DIAGNOSTIC)

    assert not final.eligible
    assert final.diagnostic_use_allowed
    assert final.constraint_ids == ("GVC-IEEE-001",)
    assert diagnostic.eligible


def test_constraint_promotion_accepts_independent_agents_without_exposing_source_advice() -> None:
    registry = GlobalValidationConstraintRegistry()
    constraint = registry.promote(
        constraint_id="GVC-002",
        claim="A validation geometry is ineligible for one evaluation purpose.",
        rule_key="diagnostic_only",
        applies_to=(ValidationUse.CANDIDATE_RANKING,),
        diagnostic_use_allowed=(ValidationGeometry.RANDOM,),
        evidence=(
            ConstraintEvidence("agent-a", "issue-x"),
            ConstraintEvidence("agent-b", "issue-x"),
        ),
    )

    assert constraint.promotion_basis == "independent_replication"
    assessed = registry.assess(_artifact(ValidationGeometry.STRICT_FORWARD), ValidationUse.CANDIDATE_RANKING)
    assert not assessed.eligible
    assert "GVC-002" in assessed.constraint_ids
    notice = constraint.agent_notice()
    assert "Model" not in notice
    assert "Score" not in notice
    assert "別の研究方向を指定" in notice


def test_constraint_promotion_requires_replication_or_safety() -> None:
    registry = GlobalValidationConstraintRegistry()
    with pytest.raises(ValueError, match="lacks independent"):
        registry.promote(
            constraint_id="GVC-weak",
            claim="weak",
            rule_key="artifact_contract",
            applies_to=(ValidationUse.CANDIDATE_RANKING,),
            diagnostic_use_allowed=(),
            evidence=(ConstraintEvidence("agent-a", "issue-x", horizons=2, seeds=3),),
        )

    promoted = registry.promote(
        constraint_id="GVC-safety",
        claim="future information is unsafe",
        rule_key="future_information",
        applies_to=(ValidationUse.CANDIDATE_RANKING,),
        diagnostic_use_allowed=(),
        evidence=(ConstraintEvidence("agent-a", "future-leak", safety_issue=True),),
    )
    assert promoted.promotion_basis == "safety"
