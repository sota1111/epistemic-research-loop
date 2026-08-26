from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from epistemic_loop.domain.enums import (
    AgentResearchState,
    CommunicationMode,
    Consequence,
    DecisionOutcome,
    Direction,
    EpistemicNiche,
    EvidenceVisibility,
    ExperimentKind,
    ExperimentStatus,
    ExperimentType,
    FailureClass,
    FalsificationDisposition,
    HoldoutAccess,
    HoldoutPolicyName,
    HypothesisStatus,
    HypothesisType,
    MaturationChildRole,
    MaturationForkStatus,
    Phase,
    Risk,
    RunMode,
    RunStatus,
    StructuralDimension,
    StructureClassification,
    StructureLifecycleState,
    TerminalStatus,
    ValidationDebtStatus,
    ValidationRequirementOutcome,
    ValidationSplitType,
    ValidationWorldStatus,
    VerifierResult,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, use_enum_values=False)


class Budget(DomainModel):
    max_experiments: int = Field(default=40, ge=1)
    max_cpu_hours: float = Field(default=120, ge=0)
    max_gpu_hours: float = Field(default=24, ge=0)
    max_wall_hours: float = Field(default=72, ge=0)
    max_llm_tokens: int = Field(default=2_000_000, ge=0)
    max_cost: float = Field(default=0, ge=0, description="0 means no monetary cap")
    max_final_submissions: int = Field(default=1, ge=0)
    #: Kaggle's per-competition daily submission allowance; the loop itself never spends it.
    max_daily_submissions: int = Field(default=5, ge=0)


class BudgetUsage(DomainModel):
    experiments: int = Field(default=0, ge=0)
    cpu_hours: float = Field(default=0, ge=0)
    gpu_hours: float = Field(default=0, ge=0)
    wall_hours: float = Field(default=0, ge=0)
    llm_tokens: int = Field(default=0, ge=0)
    cost: float = Field(default=0, ge=0)
    final_submissions: int = Field(default=0, ge=0)


class ObservedResourceUsage(DomainModel):
    cpu_hours: float | None = Field(default=None, ge=0)
    gpu_hours: float | None = Field(default=None, ge=0)
    wall_hours: float | None = Field(default=None, ge=0)
    llm_tokens: int | None = Field(default=None, ge=0)
    monetary_cost: float | None = Field(default=None, ge=0)
    peak_ram_gb: float | None = Field(default=None, ge=0)


class HoldoutPolicy(DomainModel):
    policy: HoldoutPolicyName = HoldoutPolicyName.STRICT_BLIND
    max_queries: int = Field(default=0, ge=0)
    reveal_scores: str = "after_all_paired_runs"
    sealed_store: str = ".sealed"


class ResearchRun(DomainModel):
    id: str = Field(min_length=1)
    competition_id: str = Field(min_length=1)
    primary_metric: str = Field(default="score", min_length=1)
    metric_direction: Literal["maximize", "minimize"] = "maximize"
    sample_submission: str | None = None
    max_public_queries: int = Field(default=0, ge=0)
    mode: RunMode = RunMode.EPISTEMIC
    phase: Phase = Phase.DISCOVERY
    seed: int
    status: RunStatus = RunStatus.CREATED
    base_commit_sha: str
    dataset_fingerprint: str
    config_hash: str
    budgets: Budget = Field(default_factory=Budget)
    budget_usage: BudgetUsage = Field(default_factory=BudgetUsage)
    holdout_policy: HoldoutPolicy = Field(default_factory=HoldoutPolicy)
    created_at: datetime = Field(default_factory=utc_now)
    finalized_at: datetime | None = None


class CompetitionWorldModel(DomainModel):
    target_semantics: dict[str, Any] = Field(default_factory=dict)
    metric_semantics: dict[str, Any] = Field(default_factory=dict)
    validation_assumptions: list[str] = Field(default_factory=list)
    data_generating_process: list[str] = Field(default_factory=list)
    temporal_structure: list[str] = Field(default_factory=list)
    entity_structure: list[str] = Field(default_factory=list)
    train_test_shift: list[str] = Field(default_factory=list)
    leakage_risks: list[str] = Field(default_factory=list)
    representation_hypotheses: list[str] = Field(default_factory=list)
    error_structure: list[str] = Field(default_factory=list)
    compute_constraints: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    #: What the run actually has to work with: where the data is, what runner already exists, what
    #: columns there are. The rest of this model is what the run *believes*; this is what it *has*.
    #: An experiment designer without it invents entry points and data paths, and the round is spent
    #: discovering that they do not exist.
    environment: dict[str, Any] = Field(default_factory=dict)
    version: int = Field(default=1, ge=1)


class SourceRef(DomainModel):
    id: str
    title: str
    source_type: Literal["paper", "official_docs", "competition_page", "other"]
    published_at: date | None = None
    retrieved_at: datetime = Field(default_factory=utc_now)
    competition_specific: bool = False
    allowed: bool
    policy_reason: str
    content_hash: str
    url: str | None = None


class PredictedOutcome(DomainModel):
    description: str = Field(min_length=1)
    metric_name: str = Field(min_length=1)
    expected_direction: Direction
    expected_range: dict[str, float] | None = None
    coverage_level: float | None = Field(default=None, ge=0, le=1)
    condition: str = Field(min_length=1)
    discriminates_from: list[str] = Field(default_factory=list)

    @field_validator("coverage_level")
    @classmethod
    def validate_coverage_level(cls, value: float | None) -> float | None:
        if value is not None and value not in {0.5, 0.8, 0.95}:
            raise ValueError("coverage_level must be one of 0.5, 0.8, or 0.95")
        return value


class OutcomeLikelihood(DomainModel):
    """A preregistered observable outcome under a binary research hypothesis."""

    label: str = Field(min_length=1)
    probability_if_true: float = Field(ge=0, le=1)
    probability_if_false: float = Field(ge=0, le=1)


class HypothesisOutcomeForecast(DomainModel):
    """Likelihood model used to calculate information gain without an LLM self-score.

    The hypothesis may still be proposed by a model, but the two likelihood vectors are fixed before
    execution. Selection combines them with the hypothesis probability from the event log.
    """

    hypothesis_id: str = Field(min_length=1)
    outcomes: list[OutcomeLikelihood] = Field(min_length=2)
    decisions_affected: list[str] = Field(min_length=1)
    measurement_notes: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_probability_vectors(self) -> HypothesisOutcomeForecast:
        labels = [item.label for item in self.outcomes]
        if len(labels) != len(set(labels)):
            raise ValueError("outcome likelihood labels must be unique")
        true_total = sum(item.probability_if_true for item in self.outcomes)
        false_total = sum(item.probability_if_false for item in self.outcomes)
        if abs(true_total - 1.0) > 1e-6 or abs(false_total - 1.0) > 1e-6:
            raise ValueError("outcome likelihood probabilities must sum to 1 under true and false")
        return self


class EVSIProxy(DomainModel):
    """Auditable value-of-sample-information approximation.

    The proxy is deliberately factored into the probability that a downstream
    decision changes and the utility difference between the competing actions.
    An agent cannot provide a final EVSI number independently of these inputs.
    """

    decision_change_probability: float = Field(ge=0, le=1)
    utility_difference: float = Field(ge=0, le=1)
    decision_ids: list[str] = Field(min_length=1)
    rationale: str = Field(min_length=1)

    @property
    def value(self) -> float:
        return self.decision_change_probability * self.utility_difference


class ValidationOutcomeLikelihood(DomainModel):
    label: str = Field(min_length=1)
    probability_by_world: dict[str, float] = Field(min_length=2)

    @field_validator("probability_by_world")
    @classmethod
    def valid_likelihoods(cls, value: dict[str, float]) -> dict[str, float]:
        if any(probability < 0 or probability > 1 for probability in value.values()):
            raise ValueError("validation-world outcome probabilities must be between 0 and 1")
        return value


class ValidationWorldForecast(DomainModel):
    """Preregistered categorical result distribution under each validation world."""

    outcomes: list[ValidationOutcomeLikelihood] = Field(min_length=2)
    metric_name: str = Field(min_length=1)
    decisions_affected: list[str] = Field(min_length=1)
    measurement_notes: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_world_probability_vectors(self) -> ValidationWorldForecast:
        labels = [item.label for item in self.outcomes]
        if len(labels) != len(set(labels)):
            raise ValueError("validation outcome labels must be unique")
        worlds = set(self.outcomes[0].probability_by_world)
        if any(set(item.probability_by_world) != worlds for item in self.outcomes):
            raise ValueError("every validation outcome must cover the same worlds")
        for world in worlds:
            total = sum(item.probability_by_world[world] for item in self.outcomes)
            if abs(total - 1.0) > 1e-6:
                raise ValueError(f"validation outcome probabilities for {world} must sum to 1")
        return self


class Hypothesis(DomainModel):
    id: str
    run_id: str
    type: HypothesisType
    claim: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    prior_confidence: float = Field(ge=0.05, le=0.95)
    uncalibrated_prior_confidence: float | None = Field(default=None, ge=0.05, le=0.95)
    current_confidence: float = Field(ge=0.05, le=0.95)
    confidence_kind: Literal["operational"] = "operational"
    predictions_if_true: list[PredictedOutcome] = Field(min_length=1)
    predictions_if_false: list[PredictedOutcome] = Field(min_length=1)
    alternative_hypothesis_ids: list[str] = Field(default_factory=list)
    parent_hypothesis_ids: list[str] = Field(default_factory=list)
    evidence_for: list[str] = Field(default_factory=list)
    evidence_against: list[str] = Field(default_factory=list)
    falsification_requirements: list[str] = Field(default_factory=list)
    downstream_consequence: Consequence = Consequence.MEDIUM
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    source_refs: list[SourceRef] = Field(default_factory=list)
    created_by: str
    prompt_version: str
    version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def prior_matches_first_version(self) -> Hypothesis:
        if self.version == 1 and abs(self.current_confidence - self.prior_confidence) > 1e-12:
            raise ValueError("version 1 current_confidence must equal prior_confidence")
        return self


class ScoreEstimate(DomainModel):
    #: Expected *improvement* on the run's primary metric. Positive always means better, whichever
    #: way the metric runs: for a metric that is minimised, an expected drop of 0.4 is `+0.4`. This
    #: is stated on the field because the field's JSON Schema is what the proposing model reads,
    #: and a proposal that reports a signed metric delta instead inverts its own utility -- the
    #: selector maximises expected gain and would then prefer the designs expected to do worst.
    mean_gain: float = Field(
        default=0,
        description=(
            "Expected improvement on the primary metric. Positive is always better. If the metric "
            "is minimised, report the expected reduction as a positive number."
        ),
    )
    uncertainty: float = Field(default=0, ge=0)
    fold_std: float = Field(default=0, ge=0)
    seed_std: float = Field(default=0, ge=0)
    worst_group_gap: float = Field(default=0, ge=0)
    rationale: str = ""

    def robust_gain(self, alpha: float = 1.0, beta: float = 1.0, gamma: float = 1.0) -> float:
        return self.mean_gain - alpha * self.fold_std - beta * self.seed_std - gamma * self.worst_group_gap


class EpistemicAssessment(DomainModel):
    hypothesis_discrimination: int = Field(ge=0, le=4)
    uncertainty_reduction: int = Field(ge=0, le=4)
    decision_consequence: int = Field(ge=0, le=4)
    search_space_reduction: int = Field(ge=0, le=4)
    outcome_observability: int = Field(ge=0, le=4)
    rationale: str = Field(min_length=1)

    @property
    def score(self) -> float:
        total = (
            self.hypothesis_discrimination
            + self.uncertainty_reduction
            + self.decision_consequence
            + self.search_space_reduction
            + self.outcome_observability
        )
        return total / 20.0


class RobustnessAssessment(DomainModel):
    seed_coverage: float = Field(ge=0, le=1)
    fold_coverage: float = Field(ge=0, le=1)
    subgroup_coverage: float = Field(ge=0, le=1)
    temporal_coverage: float = Field(ge=0, le=1)
    leakage_checks: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=1)

    @property
    def score(self) -> float:
        return (
            self.seed_coverage
            + self.fold_coverage
            + self.subgroup_coverage
            + self.temporal_coverage
            + self.leakage_checks
        ) / 5.0


class CostEstimate(DomainModel):
    cpu_hours: float = Field(default=0, ge=0)
    gpu_hours: float = Field(default=0, ge=0)
    wall_hours: float = Field(default=0, ge=0)
    llm_tokens: int = Field(default=0, ge=0)
    monetary_cost: float = Field(default=0, ge=0)
    failure_probability: float = Field(default=0, ge=0, le=1)


class ResourceReconciliation(DomainModel):
    run_id: str = Field(min_length=1)
    experiment_id: str = Field(min_length=1)
    estimated: CostEstimate
    observed: ObservedResourceUsage
    charged: CostEstimate


class ExperimentRetryRecord(DomainModel):
    """Auditable cost and cause of one discarded infrastructure-failure attempt."""

    id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    experiment_id: str = Field(min_length=1)
    failed_attempt: int = Field(ge=1)
    next_attempt: int = Field(ge=2)
    failure_class: FailureClass
    failure_excerpt: str | None = Field(default=None, max_length=2000)
    resource_usage: ObservedResourceUsage = Field(default_factory=ObservedResourceUsage)
    charged_cost: CostEstimate
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_retry(self) -> ExperimentRetryRecord:
        if self.failure_class != FailureClass.INFRASTRUCTURE:
            raise ValueError("only infrastructure failures may be retried automatically")
        if self.next_attempt != self.failed_attempt + 1:
            raise ValueError("next_attempt must immediately follow failed_attempt")
        return self


class AgentResourceRecord(DomainModel):
    id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    agent: str = Field(min_length=1)
    stage: Literal["hypothesis_generation", "experiment_design", "falsification_assessment"]
    model: str = Field(min_length=1)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cache_tokens: int = Field(default=0, ge=0)
    monetary_cost: float = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=utc_now)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.cache_tokens


class CandidateDescriptors(DomainModel):
    """Behavior descriptor used by the solution and epistemic QD archives."""

    validation_type: str = Field(default="random", min_length=1)
    model_family: str = Field(default="other", min_length=1)
    representation: str = Field(default="raw", min_length=1)
    data_scope: str = Field(default="train_only", min_length=1)
    shift_hypothesis: str = Field(default="none", min_length=1)
    entity_hypothesis: str = Field(default="none", min_length=1)
    error_profile: str = Field(default="global", min_length=1)
    source_agent: str = Field(default="unknown", min_length=1)
    epistemic_niche: str = Field(default="unassigned", min_length=1)
    validation_world: str = Field(default="unspecified", min_length=1)
    routing: str = Field(default="none", min_length=1)
    post_processing: str = Field(default="none", min_length=1)


class SemanticExperimentSignature(DomainModel):
    """Meaning-level identity used instead of command or experiment ID."""

    target_hypotheses: list[str] = Field(min_length=1)
    data_slice: list[str] = Field(min_length=1)
    operation: list[str] = Field(min_length=1)
    observable: list[str] = Field(min_length=1)
    decision_affected: list[str] = Field(min_length=1)
    candidate_producing: bool = False

    @field_validator("target_hypotheses", "data_slice", "operation", "observable", "decision_affected")
    @classmethod
    def normalize_signature_terms(cls, value: list[str]) -> list[str]:
        normalized = ["_".join(item.strip().lower().split()) for item in value if item.strip()]
        if not normalized:
            raise ValueError("semantic signature terms cannot be blank")
        return sorted(set(normalized))


class ReplicationSpec(DomainModel):
    original_experiment_id: str = Field(min_length=1)
    changed_condition: list[Literal["seed", "time_window", "entity_slice"]] = Field(min_length=1)
    replication_hypothesis: str = Field(min_length=1)


class DecisionBinding(DomainModel):
    decision_id: str = Field(min_length=1)
    possible_actions: list[str] = Field(min_length=2)
    result_to_action: dict[str, str] = Field(min_length=1)
    outcome: DecisionOutcome | None = None
    action_changed: bool | None = None
    action_neutral_reason: str | None = None

    @model_validator(mode="after")
    def actions_are_preregistered(self) -> DecisionBinding:
        unknown = set(self.result_to_action.values()) - set(self.possible_actions)
        if unknown:
            raise ValueError(f"result_to_action contains unregistered actions: {sorted(unknown)}")
        if self.outcome == DecisionOutcome.ACTION_NEUTRAL and not self.action_neutral_reason:
            raise ValueError("an action-neutral result requires a reason")
        return self


# ---------------------------------------------------------------------------
# C-lite v0.3: dynamically discovered structural hypotheses


class StructuralAlternative(DomainModel):
    id: str = Field(min_length=1)
    claim: str = Field(min_length=1)
    observable_predictions: list[str] = Field(min_length=1)
    falsification_conditions: list[str] = Field(min_length=1)
    null_model: bool = False


class StructureTestPreregistration(DomainModel):
    test_id: str = Field(min_length=1)
    target_hypothesis_id: str = Field(min_length=1)
    competing_hypothesis_ids: list[str] = Field(min_length=1)
    prediction_by_hypothesis: dict[str, str] = Field(min_length=2)
    falsification_condition: str = Field(min_length=1)
    confounders_preserved: list[str] = Field(min_length=1)
    decision_affected: str = Field(min_length=1)
    power_plan: str = Field(min_length=1)
    fold_safe: bool
    semantic_signature: SemanticExperimentSignature
    null_repetitions: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def predictions_cover_rivals(self) -> StructureTestPreregistration:
        expected = {self.target_hypothesis_id, *self.competing_hypothesis_ids}
        if not expected.issubset(self.prediction_by_hypothesis):
            raise ValueError("test predictions must cover the target and every competing hypothesis")
        return self


class StructuralHypothesis(DomainModel):
    id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    owner_agent: str = Field(min_length=1)
    claim: str = Field(min_length=1)
    structure_type: str = Field(min_length=1)
    observation_refs: list[str] = Field(min_length=1)
    affected_dimensions: list[StructuralDimension] = Field(default_factory=list)
    leverage_weights: dict[str, float] = Field(default_factory=dict)
    observable_predictions: list[str] = Field(default_factory=list)
    falsification_conditions: list[str] = Field(default_factory=list)
    discrimination_plan: list[str] = Field(default_factory=list)
    decisions_affected: list[str] = Field(default_factory=list)
    alternatives: list[StructuralAlternative] = Field(default_factory=list)
    preregistered_tests: list[StructureTestPreregistration] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    lifecycle_state: StructureLifecycleState = StructureLifecycleState.OBSERVATION
    classification: StructureClassification | None = None

    @field_validator("affected_dimensions")
    @classmethod
    def dimensions_are_unique(cls, value: list[StructuralDimension]) -> list[StructuralDimension]:
        if len(value) != len(set(value)):
            raise ValueError("affected structural dimensions must be unique")
        return value

    @model_validator(mode="after")
    def lifecycle_contract_is_complete(self) -> StructuralHypothesis:
        state = self.lifecycle_state
        if state != StructureLifecycleState.OBSERVATION:
            if len(self.affected_dimensions) < 2:
                raise ValueError("a structural hypothesis must affect at least two decision dimensions")
            required = {
                "observable_predictions": self.observable_predictions,
                "falsification_conditions": self.falsification_conditions,
                "discrimination_plan": self.discrimination_plan,
                "decisions_affected": self.decisions_affected,
            }
            missing = [name for name, values in required.items() if not values]
            if missing:
                raise ValueError("structural hypothesis contract is incomplete: " + ", ".join(missing))
        states_requiring_alternatives = {
            StructureLifecycleState.ALTERNATIVES_REGISTERED,
            StructureLifecycleState.DISCRIMINATING_TESTS_PREREGISTERED,
            StructureLifecycleState.PARTIALLY_VALIDATED,
            StructureLifecycleState.VALIDATED_STRUCTURE,
            StructureLifecycleState.USEFUL_ENCODING_UNVALIDATED_STRUCTURE,
            StructureLifecycleState.STRUCTURALLY_PLAUSIBLE_NON_ACTIONABLE,
            StructureLifecycleState.FALSIFIED,
            StructureLifecycleState.INCONCLUSIVE,
        }
        if state in states_requiring_alternatives and not self.alternatives:
            raise ValueError("competing structural alternatives must be registered")
        states_requiring_tests = states_requiring_alternatives - {StructureLifecycleState.ALTERNATIVES_REGISTERED}
        if state in states_requiring_tests and not self.preregistered_tests:
            raise ValueError("discriminating tests must be preregistered")
        terminal_or_partial = states_requiring_tests - {StructureLifecycleState.DISCRIMINATING_TESTS_PREREGISTERED}
        if state in terminal_or_partial and not self.evidence_refs:
            raise ValueError("partial or terminal structure states require evidence")
        return self

    @property
    def structural_leverage(self) -> float:
        if self.lifecycle_state in {StructureLifecycleState.OBSERVATION, StructureLifecycleState.PROVISIONAL_STRUCTURE}:
            return 0.0
        return sum(self.leverage_weights.get(dimension.value, 1.0) for dimension in self.affected_dimensions)


class StructureValidationDebt(DomainModel):
    debt_id: str = Field(min_length=1)
    hypothesis_id: str = Field(min_length=1)
    structure_type: str = Field(min_length=1)
    unresolved_requirements: list[str] = Field(min_length=1)
    resolution_artifacts: dict[str, str] = Field(default_factory=dict)
    resolution_outcomes: dict[str, ValidationRequirementOutcome] = Field(default_factory=dict)
    status: ValidationDebtStatus = ValidationDebtStatus.OPEN
    owner_agent: str = Field(min_length=1)
    affects_candidates: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def backfill_legacy_resolution_outcomes(cls, value: Any) -> Any:
        if not isinstance(value, dict) or "resolution_outcomes" in value:
            return value
        artifacts = value.get("resolution_artifacts")
        if not isinstance(artifacts, dict) or not artifacts:
            return value
        return {
            **value,
            "resolution_outcomes": {requirement: ValidationRequirementOutcome.PASSED for requirement in artifacts},
        }

    @model_validator(mode="after")
    def debt_state_is_consistent(self) -> StructureValidationDebt:
        if len(self.unresolved_requirements) != len(set(self.unresolved_requirements)):
            raise ValueError("validation debt requirements must be unique")
        unknown = (set(self.resolution_artifacts) | set(self.resolution_outcomes)) - set(self.unresolved_requirements)
        if unknown:
            raise ValueError(f"resolution artifacts refer to unknown requirements: {sorted(unknown)}")
        if set(self.resolution_artifacts) != set(self.resolution_outcomes):
            raise ValueError("every resolution artifact requires an explicit outcome")
        complete = set(self.resolution_artifacts) == set(self.unresolved_requirements)
        if complete != (self.status == ValidationDebtStatus.RESOLVED):
            raise ValueError("validation debt status must match requirement completion")
        return self

    @property
    def remaining_requirements(self) -> tuple[str, ...]:
        return tuple(item for item in self.unresolved_requirements if item not in self.resolution_artifacts)


class MaturationChild(DomainModel):
    child_id: str = Field(min_length=1)
    role: MaturationChildRole
    checkpoint_ref: str = Field(min_length=1)
    active: bool = True


class StructureMaturationFork(DomainModel):
    fork_id: str = Field(min_length=1)
    hypothesis_id: str = Field(min_length=1)
    owner_agent: str = Field(min_length=1)
    checkpoint_ref: str = Field(min_length=1)
    children: list[MaturationChild] = Field(min_length=3, max_length=3)
    reserved_budget_fraction: float = Field(gt=0, le=1)
    status: MaturationForkStatus = MaturationForkStatus.ACTIVE

    @model_validator(mode="after")
    def fork_has_three_distinct_functions(self) -> StructureMaturationFork:
        expected = set(MaturationChildRole)
        roles = {item.role for item in self.children}
        if roles != expected or len({item.child_id for item in self.children}) != 3:
            raise ValueError("maturation fork requires distinct implementation, null/skeptic and verification children")
        return self


class FalsificationCriticResult(DomainModel):
    test_id: str = Field(min_length=1)
    passed: bool
    checks: dict[str, bool] = Field(min_length=7)
    reasons: list[str] = Field(default_factory=list)


class StructurePromotionAssessment(DomainModel):
    hypothesis_id: str = Field(min_length=1)
    structural_validity_passed: bool
    predictive_improvement_passed: bool
    validation_debt_resolved: bool
    classification: StructureClassification | None
    lifecycle_state: StructureLifecycleState

    @model_validator(mode="after")
    def classification_matches_axes(self) -> StructurePromotionAssessment:
        if self.lifecycle_state == StructureLifecycleState.INCONCLUSIVE:
            if self.classification is not None:
                raise ValueError("an inconclusive assessment cannot assign a two-axis classification")
            return self
        expected = {
            (True, True): StructureClassification.VALIDATED_ACTIONABLE_STRUCTURE,
            (True, False): StructureClassification.VALIDATED_NON_ACTIONABLE_STRUCTURE,
            (False, True): StructureClassification.USEFUL_ENCODING_UNVALIDATED_STRUCTURE,
            (False, False): StructureClassification.REJECTED_STRUCTURE,
        }[(self.structural_validity_passed, self.predictive_improvement_passed)]
        if self.classification != expected:
            raise ValueError("structure classification does not match validity/performance axes")
        if self.structural_validity_passed and not self.validation_debt_resolved:
            raise ValueError("open validation debt prevents structural validity promotion")
        return self


class ResourceEstimate(DomainModel):
    cpu_cores: int = Field(default=1, ge=1)
    memory_gb: float = Field(default=4, gt=0)
    gpu_memory_gb: float = Field(default=0, ge=0)
    expected_minutes: float = Field(default=60, gt=0)
    parquet_scan_columns: int = Field(default=0, ge=0)
    full_table_materialization: bool = False
    heavy: bool | None = None

    @property
    def is_heavy(self) -> bool:
        return bool(
            self.heavy
            or self.full_table_materialization
            or self.parquet_scan_columns >= 100
            or self.memory_gb >= 16
            or self.gpu_memory_gb > 0
        )


class ExperimentProposal(DomainModel):
    id: str
    run_id: str
    proposer_agent: str = Field(default="experiment-designer", min_length=1)
    experiment_type: ExperimentType
    hypothesis_ids: list[str] = Field(min_length=1)
    research_question: str = Field(min_length=1)
    protocol: str = Field(min_length=1)
    controls: list[str] = Field(min_length=1)
    split_strategy: str = Field(min_length=1)
    seeds: list[int] = Field(min_length=1)
    metrics: list[str] = Field(min_length=1)
    predicted_outcomes: list[PredictedOutcome] = Field(min_length=1)
    #: Optional during the v1 -> v2 migration. New proposals should populate it; when present,
    #: selection computes mutual information from the current belief instead of trusting the
    #: proposal's 0--4 epistemic rubric.
    outcome_forecasts: list[HypothesisOutcomeForecast] = Field(default_factory=list)
    validation_world_forecast: ValidationWorldForecast | None = None
    evsi_proxy: EVSIProxy | None = None
    decision_rule: str = Field(min_length=1)
    expected_score_gain: ScoreEstimate
    epistemic_assessment: EpistemicAssessment
    robustness_assessment: RobustnessAssessment
    novelty_score: float = Field(ge=0, le=1)
    experiment_kind: ExperimentKind = ExperimentKind.DIAGNOSTIC
    candidate_producing: bool = False
    epistemic_niche: EpistemicNiche | None = None
    semantic_signature: SemanticExperimentSignature | None = None
    decision_binding: DecisionBinding | None = None
    resource_estimate: ResourceEstimate | None = None
    candidate_exception_reason: (
        Literal[
            "validation_leakage_unresolved",
            "dataset_corruption_unresolved",
            "required_observation_missing",
            "insufficient_resources",
        ]
        | None
    ) = None
    replication: ReplicationSpec | None = None
    descriptors: CandidateDescriptors | None = None
    parent_candidate_ids: list[str] = Field(default_factory=list)
    variation_operator: Literal["seed", "mutation", "crossover"] = "seed"
    falsification_proposal_id: str | None = None
    structural_hypothesis_id: str | None = None
    structure_test_id: str | None = None
    structural_leverage: float = Field(default=0, ge=0)
    discrimination_value: float = Field(default=0, ge=0, le=1)
    discrimination_values_by_prior: list[float] = Field(default_factory=list)
    validation_debt_reduction: float = Field(default=0, ge=0, le=1)
    estimated_cost: CostEstimate
    holdout_access: HoldoutAccess = HoldoutAccess.NONE
    contamination_risk: Risk = Risk.LOW
    implementation_request: dict[str, Any] = Field(
        description=(
            "How the experiment is to be carried out. What is required depends on the executor, and "
            "a proposal missing it is rejected by the hard gate before it is scored:\n"
            "- a shell executor requires `command`: the exact, runnable invocation, including every "
            "flag that fixes the split, seeds, features and output directory. It must be "
            "reproducible from this string alone.\n"
            "- an executor that directs a separate repository requires `brief`, an object with "
            "`title`, `objective`, `approach` and `verification` written in that repository's terms.\n"
            "Optional for both: `objective` (a one-line restatement), `container_image`, "
            "`resources` ({cpu, memory_gb, gpu, timeout_seconds}), `dataset_mounts` (a list of "
            "names), and `network_policy`, which must be exactly one of `disabled`, "
            "`source_policy_proxy` or `enabled` -- any other value is rejected."
        ),
    )
    required_artifacts: list[str] = Field(
        min_length=1,
        description=(
            "File names the experiment must leave in its output directory, relative and without "
            "directories -- for example `metrics.json`. These are checked for existence after the "
            "run, so a description of what a file should contain is not one of these; it belongs in "
            "the protocol. `metrics.json` is expected by every executor."
        ),
    )
    lineage: str = Field(default="default", min_length=1)
    source_refs: list[SourceRef] = Field(default_factory=list)
    status: ExperimentStatus = ExperimentStatus.PROPOSED
    is_replication_of: str | None = None
    version: int = Field(default=1, ge=1)

    @field_validator("seeds")
    @classmethod
    def unique_seeds(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("seeds must be unique")
        return value

    @field_validator("discrimination_values_by_prior")
    @classmethod
    def discrimination_values_are_probabilities(cls, value: list[float]) -> list[float]:
        if any(item < 0 or item > 1 for item in value):
            raise ValueError("prior-perturbed discrimination values must be between zero and one")
        return value

    @model_validator(mode="after")
    def validate_variation_lineage(self) -> ExperimentProposal:
        if self.variation_operator == "seed" and self.parent_candidate_ids:
            raise ValueError("seed proposals cannot declare parent candidates")
        if self.variation_operator == "mutation" and len(self.parent_candidate_ids) != 1:
            raise ValueError("mutation proposals require exactly one parent candidate")
        if self.variation_operator == "crossover" and len(self.parent_candidate_ids) != 2:
            raise ValueError("crossover proposals require exactly two parent candidates")
        if len(self.parent_candidate_ids) != len(set(self.parent_candidate_ids)):
            raise ValueError("parent candidate identifiers must be unique")
        if self.experiment_kind == ExperimentKind.CANDIDATE_PRODUCING and not self.candidate_producing:
            raise ValueError("candidate-producing experiment_kind requires candidate_producing=true")
        if (
            self.semantic_signature is not None
            and self.semantic_signature.candidate_producing != self.candidate_producing
        ):
            raise ValueError("semantic signature candidate_producing must match the proposal")
        if (
            self.experiment_type == ExperimentType.REPLICATION
            and self.replication is not None
            and self.replication.original_experiment_id != self.is_replication_of
        ):
            raise ValueError("replication identifiers must agree")
        if self.structure_test_id and not self.structural_hypothesis_id:
            raise ValueError("a structure test must identify its structural hypothesis")
        structural_utility_claimed = bool(
            self.structural_leverage
            or self.discrimination_value
            or self.discrimination_values_by_prior
            or self.validation_debt_reduction
        )
        if structural_utility_claimed and not self.structural_hypothesis_id:
            raise ValueError("structural utility requires a registered structural hypothesis")
        if (
            self.discrimination_value or self.discrimination_values_by_prior or self.validation_debt_reduction
        ) and not self.structure_test_id:
            raise ValueError("discrimination and debt-reduction utility require a preregistered structure test")
        return self

    @property
    def robust_discrimination_value(self) -> float:
        values = [self.discrimination_value, *self.discrimination_values_by_prior]
        return min(values)


class ArtifactRef(DomainModel):
    uri: str
    sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    experiment_id: str
    code_commit_sha: str
    dataset_fingerprint: str
    environment_hash: str
    content_address_sha256: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    config_hash: str = "unavailable"
    random_seeds: list[int] = Field(default_factory=list)
    mime_type: str
    size: int = Field(ge=0)
    created_at: datetime = Field(default_factory=utc_now)
    sealed: bool = False


class ValidationDiagnostics(DomainModel):
    model_rank_stability: float | None = Field(default=None, ge=-1, le=1)
    score_variance: float | None = Field(default=None, ge=0)
    pseudo_future_accuracy: float | None = Field(default=None, ge=0, le=1)
    train_valid_shift: float | None = Field(default=None, ge=0)
    leakage_risk: float | None = Field(default=None, ge=0, le=1)
    rank_reversal_rate: float | None = Field(default=None, ge=0, le=1)


class ValidationWorld(DomainModel):
    id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    split_type: ValidationSplitType
    assumptions: list[str] = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    posterior_probability: float = Field(gt=0, le=1)
    diagnostics: ValidationDiagnostics = Field(default_factory=ValidationDiagnostics)
    evidence_ids: list[str] = Field(default_factory=list)
    status: ValidationWorldStatus = ValidationWorldStatus.ACTIVE
    version: int = Field(default=1, ge=1)


class ValidationWorldEvidence(DomainModel):
    """A preregistered likelihood of one observation under every active world."""

    id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    observation_id: str = Field(min_length=1)
    likelihood_by_world: dict[str, float] = Field(min_length=2)
    reliability: float = Field(default=1, gt=0, le=1)
    metric_name: str = Field(min_length=1)
    observed_value: float
    preregistration_ref: str = Field(min_length=1)

    @field_validator("likelihood_by_world")
    @classmethod
    def positive_likelihoods(cls, value: dict[str, float]) -> dict[str, float]:
        if any(item < 0 for item in value.values()) or not any(item > 0 for item in value.values()):
            raise ValueError("world likelihoods must be non-negative with at least one positive value")
        return value


class ValidationWorldUpdate(DomainModel):
    id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    prior: dict[str, float] = Field(min_length=2)
    posterior: dict[str, float] = Field(min_length=2)
    method: Literal["bayesian_likelihood"] = "bayesian_likelihood"
    created_at: datetime = Field(default_factory=utc_now)


class FoldAssignment(DomainModel):
    world_id: str = Field(min_length=1)
    fold_id: str = Field(min_length=1)
    train_row_ids: list[str] = Field(min_length=1)
    validation_row_ids: list[str] = Field(min_length=1)
    purged_row_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def disjoint_partitions(self) -> FoldAssignment:
        for name, values in (
            ("train", self.train_row_ids),
            ("validation", self.validation_row_ids),
            ("purged", self.purged_row_ids),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"fold {name} row identifiers must be unique")
        train = set(self.train_row_ids)
        validation = set(self.validation_row_ids)
        purged = set(self.purged_row_ids)
        if train & validation or train & purged or validation & purged:
            raise ValueError("fold train, validation, and purged rows must be disjoint")
        return self


class QDCandidate(DomainModel):
    id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    experiment_id: str = Field(min_length=1)
    descriptors: CandidateDescriptors
    expected_hidden_score: float
    score_variance: float = Field(default=0, ge=0)
    normalized_cost: float = Field(default=0, ge=0)
    leakage_risk: float = Field(default=0, ge=0, le=1)
    robustness: float = Field(default=0, ge=0, le=1)
    error_diversity: float = Field(default=0, ge=0)
    artifact_ids: list[str] = Field(default_factory=list)
    oof_artifact: str | None = None
    reproduction_passed: bool = False
    leakage_check_passed: bool = False
    fold_assignment_artifact: str | None = None
    submission_procedure: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class QDArchiveEntry(DomainModel):
    cell_key: str = Field(min_length=1)
    best_quality: str
    lowest_cost: str
    highest_robustness: str
    highest_error_diversity: str


class OOFRecord(DomainModel):
    row_id: str = Field(min_length=1)
    fold_id: str = Field(min_length=1)
    target: float
    oof_prediction: float
    residual: float | None = None
    timestamp: str | None = None
    entity_id: str | None = None
    subgroup_id: str | None = None
    validation_world: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def fill_or_validate_residual(self) -> OOFRecord:
        expected = self.target - self.oof_prediction
        if self.residual is None:
            object.__setattr__(self, "residual", expected)
        elif abs(self.residual - expected) > 1e-9:
            raise ValueError("residual must equal target - oof_prediction")
        return self


class OOFArtifact(DomainModel):
    id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    validation_world: str = Field(min_length=1)
    uri: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    row_count: int = Field(ge=1)
    format: Literal["jsonl", "parquet"]
    created_at: datetime = Field(default_factory=utc_now)


class OOFEnsemble(DomainModel):
    id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    candidate_ids: list[str] = Field(min_length=2)
    validation_world: str = Field(min_length=1)
    weights: dict[str, float] = Field(min_length=2)
    fold_weights: dict[str, dict[str, float]] = Field(min_length=2)
    cross_fitted_loss: float = Field(ge=0)
    best_single_loss: float = Field(ge=0)
    marginal_gain: float
    artifact_ids: list[str] = Field(default_factory=list)
    method: Literal["cross_fitted_simplex_mse"] = "cross_fitted_simplex_mse"
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_ensemble_weights(self) -> OOFEnsemble:
        expected = set(self.candidate_ids)
        if len(expected) != len(self.candidate_ids) or set(self.weights) != expected:
            raise ValueError("ensemble weights must cover unique candidate_ids exactly")
        for fold_id, weights in self.fold_weights.items():
            if not fold_id or set(weights) != expected:
                raise ValueError("every fold weight vector must cover candidate_ids exactly")
        for weights in [self.weights, *self.fold_weights.values()]:
            if any(value < 0 or value > 1 for value in weights.values()):
                raise ValueError("ensemble weights must be between 0 and 1")
            if abs(sum(weights.values()) - 1.0) > 1e-6:
                raise ValueError("ensemble weights must sum to 1")
        return self


class FalsificationProposal(DomainModel):
    id: str = Field(min_length=1)
    target_hypothesis: str = Field(min_length=1)
    priority: float = Field(ge=0)
    attack_surface: list[str] = Field(min_length=1)
    minimal_experiment: str = Field(min_length=1)
    estimated_cpu_hours: float = Field(default=0, ge=0)
    falsification_metric: str = Field(min_length=1)
    falsification_condition: str = Field(min_length=1)
    alternative_hypothesis_id: str | None = None
    context_fields: list[str] = Field(default_factory=list)


class ResearchStateSnapshot(DomainModel):
    run_id: str
    validation_fidelity: float | None = Field(default=None, ge=0, le=1)
    validation_uncertainty: float = Field(ge=0, le=1)
    active_hypotheses: int = Field(ge=0)
    resolved_hypotheses: int = Field(ge=0)
    hypothesis_entropy_bits: float = Field(ge=0)
    hypothesis_coverage: float = Field(ge=0, le=1)
    falsification_coverage: float = Field(ge=0, le=1)
    qd_occupancy: float = Field(ge=0, le=1)
    oof_effective_rank: float = Field(ge=0)
    best_score_variance: float | None = Field(default=None, ge=0)
    expected_hidden_score: float | None = None
    expected_hidden_interval: tuple[float, float] | None = None
    hypothesis_calibration_brier: float | None = Field(default=None, ge=0)
    preferred_state_gaps: dict[str, float] = Field(default_factory=dict)
    preferred_state_total_gap: float = Field(default=0, ge=0, le=1)
    dgp_understanding: float = Field(default=0, ge=0, le=1)
    evidence_ids: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)


class FinalSelectionRule(DomainModel):
    id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    policy: Literal["final_candidate_utility_v1", "cross_fitted_ensemble_v1"]
    registered_at: datetime = Field(default_factory=utc_now)


class ForecastCalibrationRecord(DomainModel):
    id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    experiment_id: str = Field(min_length=1)
    proposer_agent: str = Field(min_length=1)
    category: str = Field(min_length=1)
    probabilities: dict[str, float] = Field(min_length=2)
    observed_label: str = Field(min_length=1)
    interval_coverage: dict[str, bool] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_probability_distribution(self) -> ForecastCalibrationRecord:
        if self.observed_label not in self.probabilities:
            raise ValueError("observed calibration label was not preregistered")
        if any(value < 0 or value > 1 for value in self.probabilities.values()):
            raise ValueError("forecast probabilities must be between 0 and 1")
        if abs(sum(self.probabilities.values()) - 1.0) > 1e-6:
            raise ValueError("forecast probabilities must sum to 1")
        return self


class CalibrationSummary(DomainModel):
    count: int = Field(ge=1)
    brier_score: float = Field(ge=0)
    log_loss: float = Field(ge=0)
    accuracy: float = Field(ge=0, le=1)
    mean_confidence: float = Field(ge=0, le=1)
    overconfidence_rate: float = Field(ge=0, le=1)
    underconfidence_rate: float = Field(ge=0, le=1)
    interval_coverage_50: float | None = Field(default=None, ge=0, le=1)
    interval_coverage_80: float | None = Field(default=None, ge=0, le=1)
    interval_coverage_95: float | None = Field(default=None, ge=0, le=1)


class Observation(DomainModel):
    id: str
    experiment_id: str
    run_id: str
    metrics: dict[str, float] = Field(default_factory=dict)
    observed_outcomes: dict[str, str] = Field(default_factory=dict)
    fold_metrics: dict[str, Any] = Field(default_factory=dict)
    seed_metrics: dict[str, Any] = Field(default_factory=dict)
    subgroup_metrics: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    code_commit_sha: str
    environment_hash: str
    dataset_fingerprint: str
    prediction_fingerprint: str | None = None
    runtime: dict[str, float] = Field(default_factory=dict)
    resource_usage: ObservedResourceUsage = Field(default_factory=ObservedResourceUsage)
    manifest_ref: str | None = None
    exit_status: str
    failure_class: FailureClass | None = None
    failure_excerpt: str | None = Field(default=None, max_length=2000)
    created_at: datetime = Field(default_factory=utc_now)


class FalsificationRecord(DomainModel):
    id: str
    hypothesis_id: str
    observation_ids: list[str] = Field(min_length=1)
    strongest_alternative_explanation: str
    confounders_checked: list[str]
    supporting_predictions_matched: list[str]
    contradicting_predictions_matched: list[str]
    disposition: FalsificationDisposition
    recommended_next_test: str | None = None
    #: Rival claims the same evidence would also explain, kept so the next round can test them.
    alternative_claims: list[str] = Field(default_factory=list)


class BeliefUpdate(DomainModel):
    id: str
    hypothesis_id: str
    prior_confidence: float = Field(ge=0.05, le=0.95)
    posterior_confidence: float = Field(ge=0.05, le=0.95)
    update_method: Literal["log_odds_evidence", "bayesian_likelihood"]
    evidence_strength: float = Field(ge=-2, le=2)
    evidence_summary: str
    observation_ids: list[str] = Field(min_length=1)
    verifier_result: VerifierResult


class DecisionRecord(DomainModel):
    id: str
    run_id: str
    candidate_experiment_ids: list[str]
    utility_breakdown: dict[str, Any]
    selected_experiment_ids: list[str]
    rejected_reasons: dict[str, list[str]]
    phase: Phase
    remaining_budget: dict[str, float | int]
    policy_version: str
    created_at: datetime = Field(default_factory=utc_now)


class ResearchBrief(DomainModel):
    run_id: str
    locked_validation_scheme: dict[str, Any]
    primary_metric: str
    robust_metric: str
    supported_hypotheses: list[str]
    falsified_hypotheses: list[str]
    unresolved_high_risk_hypotheses: list[str]
    approved_feature_families: list[str]
    approved_model_lineages: list[str]
    prohibited_shortcuts: list[str]
    required_robustness_checks: list[str]
    search_ranges: dict[str, Any]
    remaining_budget: dict[str, float | int]
    expected_failure_modes: list[str]


class ResourceRequest(DomainModel):
    cpu: int = Field(default=1, ge=1)
    memory_gb: float = Field(default=4, gt=0)
    gpu: int = Field(default=0, ge=0)
    gpu_memory_gb: float = Field(default=0, ge=0)
    timeout_seconds: int = Field(default=3600, ge=1)
    expected_minutes: float = Field(default=60, gt=0)
    parquet_scan_columns: int = Field(default=0, ge=0)
    full_table_materialization: bool = False

    def as_estimate(self) -> ResourceEstimate:
        return ResourceEstimate(
            cpu_cores=self.cpu,
            memory_gb=self.memory_gb,
            gpu_memory_gb=self.gpu_memory_gb,
            expected_minutes=self.expected_minutes,
            parquet_scan_columns=self.parquet_scan_columns,
            full_table_materialization=self.full_table_materialization,
        )


class DatasetMount(DomainModel):
    name: str = Field(min_length=1)
    read_only: Literal[True] = True


class ExperimentRequest(DomainModel):
    request_id: str = Field(min_length=1)
    experiment_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    base_commit_sha: str = Field(min_length=1)
    config_hash: str = "unavailable"
    dataset_fingerprint: str = "unavailable"
    system_mode: RunMode = RunMode.EPISTEMIC
    implementation_mode: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    #: What a shell executor runs. Empty for an executor that instructs a developer instead, which
    #: is why this is not required at the model level: whether a command is needed is the
    #: executor's contract, not a property every request has. `build_experiment_request` enforces
    #: whichever contract is actually configured.
    command: str = ""
    container_image: str = Field(min_length=1)
    dataset_mounts: list[DatasetMount]
    resources: ResourceRequest
    seeds: list[int] = Field(min_length=1)
    required_outputs: list[str] = Field(min_length=1)
    network_policy: Literal["disabled", "source_policy_proxy", "enabled"] = "disabled"
    #: Human-readable task description for an executor whose worker develops rather than executes.
    #: `command` tells a shell what to run; this tells a developer what to build and what counts as
    #: done, in the target repository's own terms.
    brief: dict[str, Any] = Field(default_factory=dict)
    candidate_producing: bool = False
    semantic_signature: SemanticExperimentSignature | None = None
    epistemic_niche: EpistemicNiche | None = None

    @model_validator(mode="after")
    def validate_execution_contract(self) -> ExperimentRequest:
        expected_prefix = f"{self.run_id}:{self.experiment_id}:"
        if not self.idempotency_key.startswith(expected_prefix):
            raise ValueError("idempotency_key must be scoped to run_id and experiment_id")
        attempt = self.idempotency_key.removeprefix(expected_prefix)
        number = attempt.removeprefix("attempt-")
        if not attempt.startswith("attempt-") or not number or number[0] not in "123456789" or not number.isdigit():
            raise ValueError("idempotency_key must end with :attempt-N")
        if len(set(self.seeds)) != len(self.seeds):
            raise ValueError("seeds must be unique")
        if any(not output or output.startswith("/") or ".." in Path(output).parts for output in self.required_outputs):
            raise ValueError("required_outputs must be safe relative paths")
        return self


class ExperimentResult(DomainModel):
    experiment_id: str
    run_id: str
    attempt: int = Field(ge=1)
    status: Literal["queued", "running", "completed", "failed"]
    terminal_status: TerminalStatus | None = None
    exit_code: int | None = None
    failure_class: FailureClass | None = None
    commit_sha: str
    environment_hash: str
    dataset_fingerprint: str
    environment_lock_hash: str = "unavailable"
    metrics: dict[str, float] = Field(default_factory=dict)
    observed_outcomes: dict[str, str] = Field(default_factory=dict)
    artifact_refs: list[str] = Field(default_factory=list)
    runtime: dict[str, float] = Field(default_factory=dict)
    resource_usage: ObservedResourceUsage = Field(default_factory=ObservedResourceUsage)
    manifest_ref: str | None = None
    external_ref: str | None = None
    failure_excerpt: str | None = Field(
        default=None,
        max_length=2000,
        description=(
            "Why the run failed, in the words of whatever failed. A failure class alone tells the "
            "next proposal that a design did not run; it does not tell it what to change."
        ),
    )

    @model_validator(mode="after")
    def assign_terminal_status(self) -> ExperimentResult:
        if self.status in {"queued", "running"}:
            if self.terminal_status is not None:
                raise ValueError("non-terminal results cannot have terminal_status")
            return self
        if self.terminal_status is None:
            inferred = TerminalStatus.COMPLETED if self.status == "completed" else TerminalStatus.FAILED_EXECUTION
            object.__setattr__(self, "terminal_status", inferred)
        if self.status == "completed" and self.terminal_status != TerminalStatus.COMPLETED:
            raise ValueError("completed transport status requires terminal_status COMPLETED")
        if self.status == "failed" and self.terminal_status == TerminalStatus.COMPLETED:
            raise ValueError("failed transport status cannot have terminal_status COMPLETED")
        return self


class ExperimentManifest(DomainModel):
    experiment_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    system_mode: RunMode
    request: ExperimentRequest
    result: ExperimentResult
    environment_lock_hash: str = Field(min_length=1)
    environment_lock_ref: str | None = None
    fold_assignment_refs: list[str] = Field(default_factory=list)
    submission_procedure: str | None = None
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime = Field(default_factory=utc_now)
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_manifest_identity(self) -> ExperimentManifest:
        if self.request.experiment_id != self.experiment_id or self.result.experiment_id != self.experiment_id:
            raise ValueError("manifest request/result experiment identity must match")
        if self.request.run_id != self.run_id or self.result.run_id != self.run_id:
            raise ValueError("manifest request/result run identity must match")
        if self.request.system_mode != self.system_mode:
            raise ValueError("manifest system mode must match its request")
        if self.result.environment_lock_hash != self.environment_lock_hash:
            raise ValueError("manifest environment lock hash must match its result")
        if self.completed_at < self.started_at:
            raise ValueError("manifest completion cannot precede its start")
        return self


# ---------------------------------------------------------------------------
# C-lite v0.2: shared control data and agent-local belief islands


class RemainingBudget(DomainModel):
    cpu_minutes: float = Field(default=0, ge=0)
    gpu_minutes: float = Field(default=0, ge=0)
    llm_tokens: int = Field(default=0, ge=0)
    wall_clock_minutes: float = Field(default=0, ge=0)


class AgentNicheAssignment(DomainModel):
    agent_id: str = Field(min_length=1)
    primary_niche: EpistemicNiche | None = None
    secondary_niche: EpistemicNiche | None = None
    dynamic_structure_discovery: bool = True

    @model_validator(mode="after")
    def niches_are_distinct(self) -> AgentNicheAssignment:
        if self.primary_niche is None and self.secondary_niche is not None:
            raise ValueError("a secondary niche requires a primary niche")
        if self.primary_niche is not None and self.secondary_niche == self.primary_niche:
            raise ValueError("primary and secondary niches must differ")
        return self


class GlobalControlState(DomainModel):
    dataset_hash: str = Field(min_length=1)
    remaining_budget: RemainingBudget = Field(default_factory=RemainingBudget)
    active_agents: list[AgentNicheAssignment] = Field(default_factory=list)
    experiment_queue: list[str] = Field(default_factory=list)
    running_experiments: list[str] = Field(default_factory=list)
    archive_occupancy: dict[str, int] = Field(default_factory=dict)
    resource_pressure: dict[str, float] = Field(default_factory=dict)
    collapse_metrics: dict[str, float] = Field(default_factory=dict)
    active_structure_forks: list[str] = Field(default_factory=list)
    open_validation_debts: list[str] = Field(default_factory=list)


class LocalHypothesisBelief(DomainModel):
    id: str = Field(min_length=1)
    claim: str = Field(min_length=1)
    prior_probability: float = Field(ge=0.05, le=0.95)
    posterior_probability: float = Field(ge=0.05, le=0.95)
    visibility: Literal["private"] = "private"


class AgentBeliefState(DomainModel):
    agent_id: str = Field(min_length=1)
    epistemic_niche: EpistemicNiche | None = None
    research_state: AgentResearchState = AgentResearchState.GENERIC_RESEARCH
    hypotheses: list[LocalHypothesisBelief] = Field(default_factory=list)
    validation_world_beliefs: dict[str, float] = Field(default_factory=dict)
    private_working_notes: list[str] = Field(default_factory=list)
    experiment_history: list[str] = Field(default_factory=list)
    rejected_hypotheses: list[str] = Field(default_factory=list)
    candidate_refs: list[str] = Field(default_factory=list)
    structural_hypothesis_refs: list[str] = Field(default_factory=list)

    @field_validator("validation_world_beliefs")
    @classmethod
    def validation_beliefs_form_distribution(cls, value: dict[str, float]) -> dict[str, float]:
        if value and (any(item < 0 for item in value.values()) or abs(sum(value.values()) - 1.0) > 1e-6):
            raise ValueError("validation_world_beliefs must be a probability distribution")
        return value


class EvidenceObservation(DomainModel):
    metric: str = Field(min_length=1)
    value: float | str | bool
    protocol: str = Field(min_length=1)


class EvidenceVerification(DomainModel):
    artifact_contract_valid: bool = False
    independently_replicated: bool = False
    observation_interpretation_separated: bool = True


class GlobalEvidence(DomainModel):
    evidence_id: str = Field(min_length=1)
    experiment_id: str = Field(min_length=1)
    producer_agent: str = Field(min_length=1)
    observation: EvidenceObservation
    artifacts: dict[str, str | None] = Field(default_factory=dict)
    verification: EvidenceVerification = Field(default_factory=EvidenceVerification)
    visibility: EvidenceVisibility = EvidenceVisibility.PRIVATE
    challenge_target_agent: str | None = None
    created_cycle: int = Field(default=0, ge=0)
    structural_hypothesis_id: str | None = None
    structure_validation_debt_open: bool = False
    interpretation: Literal[None] = None

    @model_validator(mode="after")
    def challenge_has_target(self) -> GlobalEvidence:
        if self.visibility == EvidenceVisibility.SHARED_CHALLENGE and not self.challenge_target_agent:
            raise ValueError("shared challenge evidence requires challenge_target_agent")
        return self


class EvidencePromotionRequest(DomainModel):
    evidence_id: str = Field(min_length=1)
    expected_compute_saving: bool
    diversity_risk: float = Field(ge=0, le=1)


def _challenge_hidden_fields() -> list[Literal["source_agent", "source_agent_posterior", "source_candidate_score"]]:
    return ["source_agent", "source_agent_posterior", "source_candidate_score"]


class Challenge(DomainModel):
    challenge_id: str = Field(min_length=1)
    target_agent: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    task: str = Field(min_length=1)
    hidden_fields: list[Literal["source_agent", "source_agent_posterior", "source_candidate_score"]] = Field(
        default_factory=_challenge_hidden_fields
    )


class CollapseMetrics(DomainModel):
    dominant_cluster_fraction: float = Field(ge=0, le=1)
    experiment_family_effective_count: float = Field(ge=0)
    qd_niche_occupancy: int = Field(ge=0)
    hypothesis_family_budget_fraction: float = Field(ge=0, le=1)
    mean_agent_proposal_similarity: float = Field(ge=0, le=1)
    cycle: int = Field(ge=0)


class CandidateArtifactRecord(DomainModel):
    candidate_id: str = Field(min_length=1)
    source_agent: str = Field(min_length=1)
    git_commit: str = Field(min_length=1)
    dataset_hash: str = Field(min_length=1)
    environment_hash: str = Field(min_length=1)
    artifact_root: str = Field(min_length=1)
    descriptor: CandidateDescriptors
    primary_score: float
    score_std: float = Field(default=0, ge=0)
    known_client_auc: float | None = None
    new_client_auc: float | None = None
    expected_forward_score: float | None = None
    robustness: float = Field(default=0, ge=0, le=1)
    marginal_ensemble_gain: float = 0
    uncertainty: float = Field(default=0, ge=0)
    leakage_risk: float = Field(default=0, ge=0, le=1)
    resource_cost: float = Field(default=0, ge=0)
    leakage_check_passed: bool = False
    reproducibility_passed: bool = False
    locked: bool = False
    structural_hypothesis_ids: list[str] = Field(default_factory=list)
    open_structure_validation_debt_ids: list[str] = Field(default_factory=list)


class CandidateArtifactValidation(DomainModel):
    valid: bool
    terminal_status: TerminalStatus
    missing: list[str] = Field(default_factory=list)
    invalid: list[str] = Field(default_factory=list)


class CommunicationPolicy(DomainModel):
    mode: CommunicationMode = CommunicationMode.SELECTIVE_DELAYED_ASYMMETRIC
    migration_interval_cycles: int = Field(default=3, ge=1)
    hide_source_agent_on_challenge: bool = True
    broadcast_raw_results: bool = False
    share_posteriors: Literal[False] = False
    share_global_best: Literal[False] = False
