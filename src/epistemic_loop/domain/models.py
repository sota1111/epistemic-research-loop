from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from epistemic_loop.domain.enums import (
    Consequence,
    Direction,
    ExperimentStatus,
    ExperimentType,
    FailureClass,
    FalsificationDisposition,
    HoldoutAccess,
    HoldoutPolicyName,
    HypothesisStatus,
    HypothesisType,
    Phase,
    Risk,
    RunMode,
    RunStatus,
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
    descriptors: CandidateDescriptors | None = None
    parent_candidate_ids: list[str] = Field(default_factory=list)
    variation_operator: Literal["seed", "mutation", "crossover"] = "seed"
    falsification_proposal_id: str | None = None
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
        return self


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
    timeout_seconds: int = Field(default=3600, ge=1)


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
        if any(not output or output.startswith("/") or ".." in output for output in self.required_outputs):
            raise ValueError("required_outputs must be safe relative paths")
        return self


class ExperimentResult(DomainModel):
    experiment_id: str
    run_id: str
    attempt: int = Field(ge=1)
    status: Literal["queued", "running", "completed", "failed"]
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
