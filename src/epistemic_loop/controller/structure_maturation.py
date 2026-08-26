from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from epistemic_loop.controller.falsification_critic import FalsificationTestCritic
from epistemic_loop.domain.enums import (
    MaturationChildRole,
    MaturationForkStatus,
    StructureClassification,
    StructureLifecycleState,
    ValidationDebtStatus,
)
from epistemic_loop.domain.models import (
    DomainModel,
    FalsificationCriticResult,
    MaturationChild,
    StructuralHypothesis,
    StructureMaturationFork,
    StructurePromotionAssessment,
    StructureTestPreregistration,
    StructureValidationDebt,
)

LATENT_ENTITY_DEBT_REQUIREMENTS = (
    "uid_free_ablation",
    "frequency_only_control",
    "frequency_matched_null",
    "linkage_shuffle",
    "temporal_persistence",
    "known_new_interaction",
    "multi_seed_replication",
)

GENERIC_STRUCTURE_DEBT_REQUIREMENTS = (
    "competing_hypothesis_test",
    "confounder_preserving_null",
    "independent_implication",
    "fold_safety",
    "multi_context_replication",
    "decision_adoption",
)

_ALLOWED_TRANSITIONS: Mapping[StructureLifecycleState, frozenset[StructureLifecycleState]] = {
    StructureLifecycleState.OBSERVATION: frozenset({StructureLifecycleState.PROVISIONAL_STRUCTURE}),
    StructureLifecycleState.PROVISIONAL_STRUCTURE: frozenset({StructureLifecycleState.ALTERNATIVES_REGISTERED}),
    StructureLifecycleState.ALTERNATIVES_REGISTERED: frozenset(
        {StructureLifecycleState.DISCRIMINATING_TESTS_PREREGISTERED}
    ),
    StructureLifecycleState.DISCRIMINATING_TESTS_PREREGISTERED: frozenset(
        {
            StructureLifecycleState.PARTIALLY_VALIDATED,
            StructureLifecycleState.FALSIFIED,
            StructureLifecycleState.INCONCLUSIVE,
        }
    ),
    StructureLifecycleState.PARTIALLY_VALIDATED: frozenset(
        {
            StructureLifecycleState.VALIDATED_STRUCTURE,
            StructureLifecycleState.USEFUL_ENCODING_UNVALIDATED_STRUCTURE,
            StructureLifecycleState.STRUCTURALLY_PLAUSIBLE_NON_ACTIONABLE,
            StructureLifecycleState.FALSIFIED,
            StructureLifecycleState.INCONCLUSIVE,
        }
    ),
}


class StructureAccessError(PermissionError):
    pass


class StructureMaturationController:
    """Durable scientific-validation contract around agent-local discoveries.

    Hypotheses remain owner-readable.  The controller stores only debt, fork,
    critic and promotion metadata; it never merges posteriors or tells an agent
    which structure (UID, time, graph, or otherwise) to search for.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        minimum_affected_dimensions: int = 2,
        leverage_threshold: float = 2.0,
        default_fork_budget_fraction: float = 0.15,
        critic: FalsificationTestCritic | None = None,
        debt_requirements_by_type: Mapping[str, Sequence[str]] | None = None,
    ):
        self.root = Path(root)
        self.hypothesis_root = self.root / "hypotheses"
        self.debt_root = self.root / "debts"
        self.fork_root = self.root / "forks"
        self.critic_root = self.root / "critic"
        self.assessment_root = self.root / "assessments"
        for path in (
            self.hypothesis_root,
            self.debt_root,
            self.fork_root,
            self.critic_root,
            self.assessment_root,
        ):
            path.mkdir(parents=True, exist_ok=True)
        if minimum_affected_dimensions < 2:
            raise ValueError("a structural contract requires at least two affected dimensions")
        self.minimum_affected_dimensions = minimum_affected_dimensions
        self.leverage_threshold = leverage_threshold
        self.default_fork_budget_fraction = default_fork_budget_fraction
        self.critic = critic or FalsificationTestCritic()
        self.debt_requirements_by_type = {
            "latent_entity_proxy": LATENT_ENTITY_DEBT_REQUIREMENTS,
            **(debt_requirements_by_type or {}),
        }

    def register(self, hypothesis: StructuralHypothesis, *, requester: str) -> None:
        self._authorize(hypothesis.owner_agent, requester)
        if (
            hypothesis.lifecycle_state != StructureLifecycleState.OBSERVATION
            and len(hypothesis.affected_dimensions) < self.minimum_affected_dimensions
        ):
            raise ValueError("structural hypothesis is below the configured dimension threshold")
        path = self._hypothesis_path(hypothesis.owner_agent, hypothesis.id)
        if path.exists():
            raise ValueError(f"structural hypothesis already exists: {hypothesis.id}")
        self._write(path, hypothesis)

    def get(
        self, hypothesis_id: str, *, requester: str | None = None, controller: bool = False
    ) -> StructuralHypothesis:
        path = self._find_hypothesis(hypothesis_id)
        hypothesis = StructuralHypothesis.model_validate_json(path.read_text(encoding="utf-8"))
        if not controller:
            self._authorize(hypothesis.owner_agent, requester or "")
        return hypothesis

    def advance(self, updated: StructuralHypothesis, *, requester: str) -> StructuralHypothesis:
        current = self.get(updated.id, requester=requester)
        if current.owner_agent != updated.owner_agent:
            raise StructureAccessError("structural hypothesis ownership cannot change")
        allowed = _ALLOWED_TRANSITIONS.get(current.lifecycle_state, frozenset())
        if updated.lifecycle_state not in allowed:
            raise ValueError(
                f"invalid structure transition: {current.lifecycle_state.value} -> {updated.lifecycle_state.value}"
            )
        self._write(self._hypothesis_path(updated.owner_agent, updated.id), updated)
        return updated

    def preregister_test(
        self,
        hypothesis_id: str,
        test: StructureTestPreregistration,
        *,
        requester: str,
    ) -> FalsificationCriticResult:
        hypothesis = self.get(hypothesis_id, requester=requester)
        if hypothesis.lifecycle_state not in {
            StructureLifecycleState.ALTERNATIVES_REGISTERED,
            StructureLifecycleState.DISCRIMINATING_TESTS_PREREGISTERED,
        }:
            raise ValueError("tests may be preregistered only after alternatives are registered")
        if test.target_hypothesis_id != hypothesis.id:
            raise ValueError("test target does not match the structural hypothesis")
        alternative_ids = {item.id for item in hypothesis.alternatives}
        if not set(test.competing_hypothesis_ids).issubset(alternative_ids):
            raise ValueError("test references an unregistered competing hypothesis")
        result = self.critic.review(test, existing_tests=hypothesis.preregistered_tests)
        self._write(self.critic_root / f"{self._safe(test.test_id)}.json", result)
        if not result.passed:
            return result
        updated = StructuralHypothesis.model_validate(
            {
                **hypothesis.model_dump(),
                "preregistered_tests": [*hypothesis.preregistered_tests, test],
                "lifecycle_state": StructureLifecycleState.DISCRIMINATING_TESTS_PREREGISTERED,
            }
        )
        if hypothesis.lifecycle_state == StructureLifecycleState.ALTERNATIVES_REGISTERED:
            self.advance(updated, requester=requester)
        else:
            self._write(self._hypothesis_path(updated.owner_agent, updated.id), updated)
        return result

    def record_partial_evidence(
        self,
        hypothesis_id: str,
        evidence_refs: Sequence[str],
        *,
        requester: str,
    ) -> StructuralHypothesis:
        hypothesis = self.get(hypothesis_id, requester=requester)
        updated = hypothesis.model_copy(
            update={
                "evidence_refs": list(dict.fromkeys([*hypothesis.evidence_refs, *evidence_refs])),
                "lifecycle_state": StructureLifecycleState.PARTIALLY_VALIDATED,
            }
        )
        return self.advance(updated, requester=requester)

    def create_fork(
        self,
        hypothesis_id: str,
        *,
        checkpoint_ref: str,
        requester: str,
        reserved_budget_fraction: float | None = None,
    ) -> StructureMaturationFork:
        hypothesis = self.get(hypothesis_id, requester=requester)
        if hypothesis.structural_leverage < self.leverage_threshold:
            raise ValueError("structural leverage is below the maturation threshold")
        if hypothesis.lifecycle_state not in {
            StructureLifecycleState.ALTERNATIVES_REGISTERED,
            StructureLifecycleState.DISCRIMINATING_TESTS_PREREGISTERED,
            StructureLifecycleState.PARTIALLY_VALIDATED,
        }:
            raise ValueError("maturation fork requires a registered structural alternative")
        fork_id = f"FORK-{hypothesis.id}"
        path = self.fork_root / f"{self._safe(fork_id)}.json"
        if path.exists():
            existing = StructureMaturationFork.model_validate_json(path.read_text(encoding="utf-8"))
            if existing.status == MaturationForkStatus.ACTIVE:
                raise ValueError("an active maturation fork already exists")
        children = [
            MaturationChild(
                child_id=f"{fork_id}-{role.value}",
                role=role,
                checkpoint_ref=checkpoint_ref,
            )
            for role in MaturationChildRole
        ]
        fork = StructureMaturationFork(
            fork_id=fork_id,
            hypothesis_id=hypothesis.id,
            owner_agent=hypothesis.owner_agent,
            checkpoint_ref=checkpoint_ref,
            children=children,
            reserved_budget_fraction=reserved_budget_fraction or self.default_fork_budget_fraction,
        )
        self._write(path, fork)
        return fork

    def dissolve_fork(self, fork_id: str, *, requester: str) -> StructureMaturationFork:
        path = self.fork_root / f"{self._safe(fork_id)}.json"
        if not path.is_file():
            raise KeyError(f"unknown maturation fork: {fork_id}")
        fork = StructureMaturationFork.model_validate_json(path.read_text(encoding="utf-8"))
        self._authorize(fork.owner_agent, requester)
        updated = fork.model_copy(
            update={
                "status": MaturationForkStatus.DISSOLVED,
                "children": [item.model_copy(update={"active": False}) for item in fork.children],
            }
        )
        self._write(path, updated)
        return updated

    def open_debt(
        self,
        hypothesis_id: str,
        *,
        candidate_id: str,
        requester: str,
    ) -> StructureValidationDebt:
        hypothesis = self.get(hypothesis_id, requester=requester)
        debt_id = f"DEBT-{hypothesis.id}"
        path = self.debt_root / f"{self._safe(debt_id)}.json"
        if path.exists():
            debt = StructureValidationDebt.model_validate_json(path.read_text(encoding="utf-8"))
            candidates = list(dict.fromkeys([*debt.affects_candidates, candidate_id]))
            updated = debt.model_copy(update={"affects_candidates": candidates})
            self._write(path, updated)
            return updated
        requirements = self.debt_requirements_by_type.get(
            hypothesis.structure_type, GENERIC_STRUCTURE_DEBT_REQUIREMENTS
        )
        debt = StructureValidationDebt(
            debt_id=debt_id,
            hypothesis_id=hypothesis.id,
            structure_type=hypothesis.structure_type,
            unresolved_requirements=list(requirements),
            owner_agent=hypothesis.owner_agent,
            affects_candidates=[candidate_id],
        )
        self._write(path, debt)
        return debt

    def debt(
        self, hypothesis_id: str, *, controller: bool = False, requester: str | None = None
    ) -> StructureValidationDebt:
        path = self.debt_root / f"{self._safe(f'DEBT-{hypothesis_id}')}.json"
        if not path.is_file():
            raise KeyError(f"no validation debt for structural hypothesis: {hypothesis_id}")
        debt = StructureValidationDebt.model_validate_json(path.read_text(encoding="utf-8"))
        if not controller:
            self._authorize(debt.owner_agent, requester or "")
        return debt

    def resolve_requirement(
        self,
        hypothesis_id: str,
        requirement: str,
        *,
        artifact_ref: str,
        requester: str,
    ) -> StructureValidationDebt:
        debt = self.debt(hypothesis_id, requester=requester)
        if requirement not in debt.unresolved_requirements:
            raise ValueError(f"unknown validation debt requirement: {requirement}")
        artifacts = {**debt.resolution_artifacts, requirement: artifact_ref}
        status = (
            ValidationDebtStatus.RESOLVED
            if set(artifacts) == set(debt.unresolved_requirements)
            else ValidationDebtStatus.OPEN
        )
        updated = debt.model_copy(update={"resolution_artifacts": artifacts, "status": status})
        self._write(self.debt_root / f"{self._safe(debt.debt_id)}.json", updated)
        return updated

    def assess_promotion(
        self,
        hypothesis_id: str,
        *,
        structural_validity_passed: bool,
        predictive_improvement_passed: bool,
        evidence_refs: Sequence[str],
        requester: str,
        conclusive: bool = True,
    ) -> StructurePromotionAssessment:
        hypothesis = self.get(hypothesis_id, requester=requester)
        try:
            debt = self.debt(hypothesis_id, requester=requester)
            debt_resolved = debt.status == ValidationDebtStatus.RESOLVED
        except KeyError:
            debt_resolved = False
        effective_validity = structural_validity_passed and debt_resolved
        if not conclusive:
            lifecycle = StructureLifecycleState.INCONCLUSIVE
            classification = None
        elif effective_validity:
            classification = (
                StructureClassification.VALIDATED_ACTIONABLE_STRUCTURE
                if predictive_improvement_passed
                else StructureClassification.VALIDATED_NON_ACTIONABLE_STRUCTURE
            )
            lifecycle = (
                StructureLifecycleState.VALIDATED_STRUCTURE
                if predictive_improvement_passed
                else StructureLifecycleState.STRUCTURALLY_PLAUSIBLE_NON_ACTIONABLE
            )
        elif predictive_improvement_passed:
            classification = StructureClassification.USEFUL_ENCODING_UNVALIDATED_STRUCTURE
            lifecycle = StructureLifecycleState.USEFUL_ENCODING_UNVALIDATED_STRUCTURE
        else:
            classification = StructureClassification.REJECTED_STRUCTURE
            lifecycle = StructureLifecycleState.FALSIFIED
        assessment = StructurePromotionAssessment(
            hypothesis_id=hypothesis.id,
            structural_validity_passed=effective_validity,
            predictive_improvement_passed=predictive_improvement_passed,
            validation_debt_resolved=debt_resolved,
            classification=classification,
            lifecycle_state=lifecycle,
        )
        updated = hypothesis.model_copy(
            update={
                "evidence_refs": list(dict.fromkeys([*hypothesis.evidence_refs, *evidence_refs])),
                "lifecycle_state": lifecycle,
                "classification": classification,
            }
        )
        self.advance(updated, requester=requester)
        self._write(
            self.assessment_root / f"{self._safe(hypothesis.id)}.json",
            assessment,
        )
        return assessment

    def can_share_as_confirmed_fact(self, hypothesis_id: str) -> bool:
        hypothesis = self.get(hypothesis_id, controller=True)
        if hypothesis.lifecycle_state != StructureLifecycleState.VALIDATED_STRUCTURE:
            return False
        try:
            return self.debt(hypothesis_id, controller=True).status == ValidationDebtStatus.RESOLVED
        except KeyError:
            return False

    def open_debt_ids(self) -> tuple[str, ...]:
        return tuple(sorted(item.debt_id for item in self.all_debts() if item.status == ValidationDebtStatus.OPEN))

    def all_debts(self) -> tuple[StructureValidationDebt, ...]:
        return tuple(
            StructureValidationDebt.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(self.debt_root.glob("*.json"))
        )

    def all_assessments(self) -> tuple[StructurePromotionAssessment, ...]:
        return tuple(
            StructurePromotionAssessment.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(self.assessment_root.glob("*.json"))
        )

    def active_fork_ids(self) -> tuple[str, ...]:
        forks = (
            StructureMaturationFork.model_validate_json(path.read_text(encoding="utf-8"))
            for path in self.fork_root.glob("*.json")
        )
        return tuple(sorted(item.fork_id for item in forks if item.status == MaturationForkStatus.ACTIVE))

    def _find_hypothesis(self, hypothesis_id: str) -> Path:
        safe = self._safe(hypothesis_id)
        matches = list(self.hypothesis_root.glob(f"*/{safe}.json"))
        if not matches:
            raise KeyError(f"unknown structural hypothesis: {hypothesis_id}")
        if len(matches) > 1:
            raise ValueError(f"structural hypothesis identifier is not globally unique: {hypothesis_id}")
        return matches[0]

    def _hypothesis_path(self, owner: str, identifier: str) -> Path:
        directory = self.hypothesis_root / self._safe(owner)
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{self._safe(identifier)}.json"

    @staticmethod
    def _authorize(owner: str, requester: str) -> None:
        if owner != requester:
            raise StructureAccessError("agent-local structural hypotheses are not cross-readable")

    @staticmethod
    def _safe(identifier: str) -> str:
        if not identifier or Path(identifier).name != identifier:
            raise ValueError("identifier must be a safe path component")
        return identifier

    @staticmethod
    def _write(path: Path, model: DomainModel) -> None:
        payload = model.model_dump_json(indent=2)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(payload + "\n", encoding="utf-8")
        temporary.replace(path)
