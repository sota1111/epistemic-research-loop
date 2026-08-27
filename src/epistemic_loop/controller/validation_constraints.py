"""Outcome-neutral validation eligibility constraints for v0.3.4."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum


class ValidationGeometry(StrEnum):
    STRICT_FORWARD = "strict_forward"
    SHUFFLED = "shuffled"
    RANDOM = "random"


class ValidationUse(StrEnum):
    FINAL_CANDIDATE_POOL = "final_candidate_pool"
    PREDICTIVE_DIVERSITY_ARCHIVE = "predictive_diversity_archive"
    ENSEMBLE_WEIGHT_LEARNING = "ensemble_weight_learning"
    CANDIDATE_RANKING = "candidate_ranking"
    DIAGNOSTIC = "diagnostic"


FINAL_FUTURE_TRANSPORT_USES = frozenset(
    {
        ValidationUse.FINAL_CANDIDATE_POOL,
        ValidationUse.PREDICTIVE_DIVERSITY_ARCHIVE,
        ValidationUse.ENSEMBLE_WEIGHT_LEARNING,
        ValidationUse.CANDIDATE_RANKING,
    }
)

SUPPORTED_RULE_KEYS = frozenset(
    {
        "strict_forward_required_for_future_transport",
        "diagnostic_only",
        "future_information",
        "fold_train_only",
        "artifact_contract",
        "leakage_safe",
    }
)


@dataclass(frozen=True)
class ValidationArtifactDescriptor:
    candidate_id: str
    geometry: ValidationGeometry
    past_only: bool
    fold_train_only_feature_fit: bool
    artifact_contract_valid: bool
    leakage_check_passed: bool


@dataclass(frozen=True)
class ValidationEligibility:
    eligible: bool
    diagnostic_use_allowed: bool
    reasons: tuple[str, ...]
    constraint_ids: tuple[str, ...]


@dataclass(frozen=True)
class ConstraintEvidence:
    agent_id: str
    issue_key: str
    horizons: int = 0
    seeds: int = 0
    same_direction: bool = False
    artifact_gate_passed: bool = False
    independent_verifier_passed: bool = False
    safety_issue: bool = False


@dataclass(frozen=True)
class GlobalValidationConstraint:
    constraint_id: str
    claim: str
    rule_key: str
    applies_to: tuple[ValidationUse, ...]
    diagnostic_use_allowed: tuple[ValidationGeometry, ...]
    promotion_basis: str

    def agent_notice(self) -> str:
        return (
            "この評価GeometryはFinal Future-transport Poolの資格条件を満たしません。"
            "別の研究方向を指定するものではありません。"
        )


GVC_IEEE_001 = GlobalValidationConstraint(
    constraint_id="GVC-IEEE-001",
    claim="Future-transport candidate selection requires past-only strict-forward OOF predictions.",
    rule_key="strict_forward_required_for_future_transport",
    applies_to=tuple(sorted(FINAL_FUTURE_TRANSPORT_USES, key=str)),
    diagnostic_use_allowed=(ValidationGeometry.SHUFFLED, ValidationGeometry.RANDOM),
    promotion_basis="frozen_infrastructure_constraint",
)


class GlobalValidationConstraintRegistry:
    """Store eligibility rules without carrying source scores or solution advice."""

    def __init__(self, constraints: Sequence[GlobalValidationConstraint] = (GVC_IEEE_001,)):
        self._constraints = {item.constraint_id: item for item in constraints}
        if len(self._constraints) != len(constraints):
            raise ValueError("constraint identifiers must be unique")

    @property
    def constraints(self) -> tuple[GlobalValidationConstraint, ...]:
        return tuple(self._constraints[key] for key in sorted(self._constraints))

    def assess(self, artifact: ValidationArtifactDescriptor, use: ValidationUse) -> ValidationEligibility:
        reasons: list[str] = []
        constraint_ids: list[str] = []
        if not artifact.artifact_contract_valid:
            reasons.append("artifact_contract_invalid")
        if not artifact.leakage_check_passed:
            reasons.append("leakage_check_failed")
        for constraint in self.constraints:
            if use not in constraint.applies_to:
                continue
            violated = False
            if constraint.rule_key == "strict_forward_required_for_future_transport":
                violated = (
                    artifact.geometry is not ValidationGeometry.STRICT_FORWARD
                    or not artifact.past_only
                    or not artifact.fold_train_only_feature_fit
                )
                reason = "strict_forward_oof_required"
            elif constraint.rule_key == "diagnostic_only":
                violated = True
                reason = "geometry_is_diagnostic_only"
            elif constraint.rule_key == "future_information":
                violated = not artifact.past_only
                reason = "future_information_detected"
            elif constraint.rule_key == "fold_train_only":
                violated = not artifact.fold_train_only_feature_fit
                reason = "feature_fit_crosses_fold_boundary"
            elif constraint.rule_key == "artifact_contract":
                violated = not artifact.artifact_contract_valid
                reason = "artifact_contract_invalid"
            else:
                violated = not artifact.leakage_check_passed
                reason = "leakage_check_failed"
            if violated:
                reasons.append(reason)
                constraint_ids.append(constraint.constraint_id)
        return ValidationEligibility(
            eligible=not reasons,
            diagnostic_use_allowed=(
                artifact.artifact_contract_valid
                and artifact.leakage_check_passed
                and (
                    artifact.geometry in {ValidationGeometry.SHUFFLED, ValidationGeometry.RANDOM}
                    or artifact.geometry is ValidationGeometry.STRICT_FORWARD
                )
            ),
            reasons=tuple(dict.fromkeys(reasons)),
            constraint_ids=tuple(dict.fromkeys(constraint_ids)),
        )

    def promote(
        self,
        *,
        constraint_id: str,
        claim: str,
        rule_key: str,
        applies_to: Sequence[ValidationUse],
        diagnostic_use_allowed: Sequence[ValidationGeometry],
        evidence: Sequence[ConstraintEvidence],
    ) -> GlobalValidationConstraint:
        if constraint_id in self._constraints:
            raise ValueError(f"constraint already exists: {constraint_id}")
        if rule_key not in SUPPORTED_RULE_KEYS:
            raise ValueError(f"unsupported validation constraint rule: {rule_key}")
        if not evidence:
            raise ValueError("constraint promotion requires evidence")
        issue_keys = {item.issue_key for item in evidence}
        if len(issue_keys) != 1:
            raise ValueError("constraint evidence must address one validation issue")
        independent_agents = {item.agent_id for item in evidence}
        condition_a = len(independent_agents) >= 2
        condition_b = any(
            item.horizons >= 3
            and item.seeds >= 3
            and item.same_direction
            and item.artifact_gate_passed
            and item.independent_verifier_passed
            for item in evidence
        )
        condition_c = any(item.safety_issue for item in evidence)
        if not (condition_a or condition_b or condition_c):
            raise ValueError("constraint lacks independent replication, strong replication, or safety evidence")
        if condition_a:
            basis = "independent_replication"
        elif condition_b:
            basis = "strong_single_agent_replication"
        else:
            basis = "safety"
        constraint = GlobalValidationConstraint(
            constraint_id=constraint_id,
            claim=claim,
            rule_key=rule_key,
            applies_to=tuple(applies_to),
            diagnostic_use_allowed=tuple(diagnostic_use_allowed),
            promotion_basis=basis,
        )
        self._constraints[constraint_id] = constraint
        return constraint
