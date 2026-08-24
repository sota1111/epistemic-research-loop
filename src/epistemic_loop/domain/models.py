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


class BudgetUsage(DomainModel):
    experiments: int = Field(default=0, ge=0)
    cpu_hours: float = Field(default=0, ge=0)
    gpu_hours: float = Field(default=0, ge=0)
    wall_hours: float = Field(default=0, ge=0)
    llm_tokens: int = Field(default=0, ge=0)
    cost: float = Field(default=0, ge=0)
    final_submissions: int = Field(default=0, ge=0)


class HoldoutPolicy(DomainModel):
    policy: HoldoutPolicyName = HoldoutPolicyName.STRICT_BLIND
    max_queries: int = Field(default=0, ge=0)
    reveal_scores: str = "after_all_paired_runs"
    sealed_store: str = ".sealed"


class ResearchRun(DomainModel):
    id: str = Field(min_length=1)
    competition_id: str = Field(min_length=1)
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
    condition: str = Field(min_length=1)
    discriminates_from: list[str] = Field(default_factory=list)


class Hypothesis(DomainModel):
    id: str
    run_id: str
    type: HypothesisType
    claim: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    prior_confidence: float = Field(ge=0.05, le=0.95)
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
    mean_gain: float = 0
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


class ExperimentProposal(DomainModel):
    id: str
    run_id: str
    experiment_type: ExperimentType
    hypothesis_ids: list[str] = Field(min_length=1)
    research_question: str = Field(min_length=1)
    protocol: str = Field(min_length=1)
    controls: list[str] = Field(min_length=1)
    split_strategy: str = Field(min_length=1)
    seeds: list[int] = Field(min_length=1)
    metrics: list[str] = Field(min_length=1)
    predicted_outcomes: list[PredictedOutcome] = Field(min_length=1)
    decision_rule: str = Field(min_length=1)
    expected_score_gain: ScoreEstimate
    epistemic_assessment: EpistemicAssessment
    robustness_assessment: RobustnessAssessment
    novelty_score: float = Field(ge=0, le=1)
    estimated_cost: CostEstimate
    holdout_access: HoldoutAccess = HoldoutAccess.NONE
    contamination_risk: Risk = Risk.LOW
    implementation_request: dict[str, Any]
    required_artifacts: list[str] = Field(min_length=1)
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


class ArtifactRef(DomainModel):
    uri: str
    sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    experiment_id: str
    code_commit_sha: str
    dataset_fingerprint: str
    environment_hash: str
    mime_type: str
    size: int = Field(ge=0)
    created_at: datetime = Field(default_factory=utc_now)
    sealed: bool = False


class Observation(DomainModel):
    id: str
    experiment_id: str
    run_id: str
    metrics: dict[str, float] = Field(default_factory=dict)
    fold_metrics: dict[str, Any] = Field(default_factory=dict)
    seed_metrics: dict[str, Any] = Field(default_factory=dict)
    subgroup_metrics: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    code_commit_sha: str
    environment_hash: str
    dataset_fingerprint: str
    prediction_fingerprint: str | None = None
    runtime: dict[str, float] = Field(default_factory=dict)
    exit_status: str
    failure_class: FailureClass | None = None
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
    implementation_mode: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    command: str = Field(min_length=1)
    container_image: str = Field(min_length=1)
    dataset_mounts: list[DatasetMount]
    resources: ResourceRequest
    seeds: list[int] = Field(min_length=1)
    required_outputs: list[str] = Field(min_length=1)
    network_policy: Literal["disabled", "source_policy_proxy", "enabled"] = "disabled"

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
    metrics: dict[str, float] = Field(default_factory=dict)
    artifact_refs: list[str] = Field(default_factory=list)
    runtime: dict[str, float] = Field(default_factory=dict)
    external_ref: str | None = None
