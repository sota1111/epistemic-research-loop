from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from epistemic_loop.domain.enums import (
    CommunicationMode,
    EpistemicNiche,
    LeaderboardFeedbackMode,
    Phase,
    RunMode,
    ValidationSplitType,
)
from epistemic_loop.domain.models import Budget, HoldoutPolicy

_ENV_PATTERN = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")


def _expand_env(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _expand_env(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    if not isinstance(value, str):
        return value

    def substitute(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in os.environ:
            raise ValueError(f"required environment variable is not set: {name}")
        return os.environ[name]

    return _ENV_PATTERN.sub(substitute, value)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunConfig(StrictModel):
    id: str | None = None
    mode: RunMode = RunMode.EPISTEMIC
    seed: int = 101


class SystemConfig(StrictModel):
    mode: RunMode = RunMode.SYSTEM_C
    communication_mode: CommunicationMode = CommunicationMode.SELECTIVE_DELAYED_ASYMMETRIC
    max_cycles: int = Field(default=12, ge=1)


class AgentIslandConfig(StrictModel):
    count: int = Field(default=4, ge=1)
    belief_scope: Literal["local"] = "local"
    share_posteriors: Literal[False] = False
    share_global_best: Literal[False] = False
    dynamic_structure_discovery: Literal[True] = True
    fixed_structure_roles: Literal[False] = False
    niches: list[EpistemicNiche] = Field(default_factory=list)


class CommunicationConfig(StrictModel):
    store_all_evidence_globally: bool = True
    broadcast_raw_results: Literal[False] = False
    broadcast_verified_facts: Literal["selective", "none", "full"] = "selective"
    migration_interval_cycles: int = Field(default=3, ge=1)
    challenge_sharing: bool = True
    hide_source_agent_on_challenge: bool = True


class DiversityConfig(StrictModel):
    semantic_duplicate_detection: bool = True
    duplicate_similarity_threshold: float = Field(default=0.85, ge=0, le=1)
    minimum_niche_budget_enabled: bool = False
    global_best_visibility: Literal["controller_only"] = "controller_only"
    collapse_detection: bool = True
    collapse_consecutive_cycles: int = Field(default=2, ge=1)
    dominant_cluster_threshold: float = Field(default=0.70, ge=0, le=1)
    effective_family_floor: float = Field(default=2.0, ge=0)
    hypothesis_budget_threshold: float = Field(default=0.50, ge=0, le=1)
    mean_similarity_threshold: float = Field(default=0.80, ge=0, le=1)
    niche_budget: dict[str, float] = Field(
        default_factory=lambda: {
            "temporal": 0.15,
            "entity_client": 0.15,
            "validation": 0.15,
            "distribution_shift": 0.10,
            "feature_representation": 0.15,
            "model_family": 0.10,
            "falsification": 0.10,
            "post_processing_ensemble": 0.10,
        }
    )

    @model_validator(mode="after")
    def validate_niche_budget(self) -> DiversityConfig:
        if any(value < 0 or value > 1 for value in self.niche_budget.values()):
            raise ValueError("niche budget fractions must be between zero and one")
        if abs(sum(self.niche_budget.values()) - 1.0) > 1e-6:
            raise ValueError("niche budget fractions must sum to one")
        return self


class ActionSpaceConfig(StrictModel):
    allow_new_python_scripts: bool = True
    allow_pipeline_modification: bool = True
    allow_new_models: bool = True
    allow_new_features: bool = True
    allow_new_uid_candidates: bool = True
    allow_post_processing: bool = True
    allow_ensembles: bool = True


class PhaseGateConfig(StrictModel):
    max_consecutive_diagnostic_experiments: int = Field(default=3, ge=1)
    require_candidate_after_diagnostics: bool = True
    candidate_exception_requires_reason: bool = True


class CandidateArchiveConfig(StrictModel):
    portfolio_size: int = Field(default=24, ge=8, le=40)
    minimum_candidate_slots: int = Field(default=8, ge=8, le=40)
    maximum_candidate_slots: int = Field(default=40, ge=8, le=40)
    minimum_niche_slots: int = Field(default=1, ge=1)
    keep_best_per_niche: bool = True
    hide_other_candidate_scores_from_agents: bool = True

    @model_validator(mode="after")
    def validate_archive_size(self) -> CandidateArchiveConfig:
        if self.minimum_candidate_slots > self.portfolio_size:
            raise ValueError("portfolio_size must cover minimum_candidate_slots")
        if self.portfolio_size > self.maximum_candidate_slots:
            raise ValueError("portfolio_size cannot exceed maximum_candidate_slots")
        return self


class SchedulerConfig(StrictModel):
    max_concurrent_heavy_experiments: int = Field(default=1, ge=1)
    max_concurrent_light_experiments: int = Field(default=3, ge=1)
    memory_safety_margin: float = Field(default=0.25, ge=0, lt=1)
    validate_required_artifacts: bool = True
    total_memory_gb: float | None = Field(default=None, gt=0)
    total_gpu_memory_gb: float = Field(default=0, ge=0)
    max_concurrent_parquet_full_scans: int = Field(default=1, ge=1)


class EvaluationConfig(StrictModel):
    primary: Literal["locked_hidden_performance"] = "locked_hidden_performance"
    secondary: list[str] = Field(
        default_factory=lambda: [
            "forward_validation",
            "critical_discovery",
            "top_solution_rubric",
            "semantic_duplicate_rate",
            "qd_occupancy",
            "error_diversity",
            "ensemble_gain",
        ]
    )


class CompetitionConfig(StrictModel):
    slug: str
    metric_direction: Literal["maximize", "minimize"]
    primary_metric: str = "score"
    data_path: str | None = None
    sample_submission: str | None = None


class LoopConfig(StrictModel):
    phase_policy: str = "adaptive"
    max_active_hypotheses: int = Field(default=30, ge=1)
    max_priority_hypotheses: int = Field(default=10, ge=1)
    #: Consecutive optimization experiments allowed before a non-optimization run is required.
    #: 0 disables the rule; an exploiter-only control arm sets it to 0 so it can be an exploiter.
    max_consecutive_optimization_experiments: int = Field(default=3, ge=0)
    minimum_replications_for_support: int = Field(default=1, ge=1)
    #: Selecting queries one validation scheme may answer before it must be rotated. 0 disables.
    max_validation_reuse: int = Field(default=8, ge=0)
    #: Rounds that may produce no new observation before the loop stops instead of spinning.
    max_rounds_without_information: int = Field(default=3, ge=1)
    #: Seed/fold spread above which an exploitation result counts as an anomaly and returns the run.
    anomaly_instability_threshold: float = Field(default=0.05, ge=0)


class PhaseWeights(StrictModel):
    pragmatic: float = Field(ge=0)
    epistemic: float = Field(ge=0)
    robustness: float = Field(ge=0)
    diversity: float = Field(ge=0)
    structural_leverage: float = Field(default=0, ge=0)
    discrimination: float = Field(default=0, ge=0)
    validation_debt_reduction: float = Field(default=0, ge=0)


class StructureDiscoveryConfig(StrictModel):
    enabled: Literal[True] = True
    fixed_structure_roles: Literal[False] = False
    minimum_affected_dimensions: int = Field(default=2, ge=2)
    maturation_leverage_threshold: float = Field(default=2.0, ge=0)
    maturation_budget_fraction: float = Field(default=0.15, gt=0, le=1)
    require_stateless_critic: Literal[True] = True
    require_competing_hypotheses: Literal[True] = True
    matched_null_repetitions: int = Field(default=20, ge=20)
    forward_horizons: int = Field(default=3, ge=3)
    replication_seeds: int = Field(default=3, ge=3)
    bootstrap_confidence: float = Field(default=0.95, gt=0.5, lt=1)
    matched_null_quantile: float = Field(default=0.95, gt=0.5, lt=1)
    latent_entity_debt_requirements: list[str] = Field(
        default_factory=lambda: [
            "uid_free_ablation",
            "frequency_only_control",
            "frequency_matched_null",
            "linkage_shuffle",
            "temporal_persistence",
            "known_new_interaction",
            "multi_seed_replication",
        ],
        min_length=1,
    )


class PortfolioAllocation(StrictModel):
    exploit: float = Field(ge=0, le=1)
    qd_explore: float = Field(ge=0, le=1)
    epistemic: float = Field(ge=0, le=1)

    def model_post_init(self, __context: Any) -> None:
        if abs(self.exploit + self.qd_explore + self.epistemic - 1.0) > 1e-6:
            raise ValueError("portfolio allocation fractions must sum to 1")


class SelectionConfig(StrictModel):
    cost_lambda: float = Field(default=0.15, ge=0)
    risk_lambda: float = Field(default=0.5, ge=0)
    minimum_utility: float = 0.0
    eig_method: Literal["exact", "monte_carlo"] = "monte_carlo"
    eig_monte_carlo_samples: int = Field(default=4000, ge=100)
    discovery: PhaseWeights = PhaseWeights(
        pragmatic=0.20,
        epistemic=0.45,
        robustness=0.20,
        diversity=0.15,
        structural_leverage=0.20,
        discrimination=0.25,
        validation_debt_reduction=0.15,
    )
    consolidation: PhaseWeights = PhaseWeights(
        pragmatic=0.35,
        epistemic=0.30,
        robustness=0.25,
        diversity=0.10,
        structural_leverage=0.15,
        discrimination=0.25,
        validation_debt_reduction=0.25,
    )
    exploitation: PhaseWeights = PhaseWeights(
        pragmatic=0.55,
        epistemic=0.15,
        robustness=0.25,
        diversity=0.05,
        structural_leverage=0.10,
        discrimination=0.15,
        validation_debt_reduction=0.30,
    )
    discovery_allocation: PortfolioAllocation = PortfolioAllocation(exploit=0.30, qd_explore=0.30, epistemic=0.40)
    consolidation_allocation: PortfolioAllocation = PortfolioAllocation(exploit=0.45, qd_explore=0.30, epistemic=0.25)
    exploitation_allocation: PortfolioAllocation = PortfolioAllocation(exploit=0.65, qd_explore=0.25, epistemic=0.10)

    def for_phase(self, phase: Phase) -> PhaseWeights:
        if phase == Phase.DISCOVERY:
            return self.discovery
        if phase == Phase.CONSOLIDATION:
            return self.consolidation
        return self.exploitation

    def allocation_for_phase(self, phase: Phase) -> PortfolioAllocation:
        if phase == Phase.DISCOVERY:
            return self.discovery_allocation
        if phase == Phase.CONSOLIDATION:
            return self.consolidation_allocation
        return self.exploitation_allocation


class ValidationConfig(StrictModel):
    worlds: list[ValidationSplitType] = Field(
        default_factory=lambda: [ValidationSplitType.RANDOM, ValidationSplitType.TIME, ValidationSplitType.GROUP],
        min_length=2,
    )
    entropy_priority_threshold: float = Field(default=0.65, ge=0, le=1)
    require_forward_fraud_label_validation: bool = True
    horizons: int = Field(default=3, ge=3)
    require_time_gap: bool = True
    require_known_new_client_slices: bool = True
    adversarial_auc_is_diagnostic_only: Literal[True] = True


class QDConfig(StrictModel):
    maximum_archive_size: int = Field(default=100, ge=1)
    quality_floor_relative_to_best: float = Field(default=0.97, ge=0, le=1)


class OOFConfig(StrictModel):
    save_row_level_predictions: bool = True
    format: str = Field(default="parquet", pattern="^(parquet|jsonl)$")
    required_for_candidate_promotion: bool = True
    common_final_crossfit: bool = True
    calculate_residual_correlation: bool = True
    calculate_effective_rank: bool = True
    calculate_marginal_ensemble_gain: bool = True


class CalibrationConfig(StrictModel):
    enabled: bool = True
    minimum_records: int = Field(default=3, ge=1)
    poor_brier_threshold: float = Field(default=0.25, ge=0)
    prior_shrinkage: float = Field(default=0.25, ge=0, le=1)


class PreferredStateConfig(StrictModel):
    targets: dict[str, float] = Field(
        default_factory=lambda: {
            "validation_fidelity": 0.80,
            "hypothesis_resolution": 0.70,
            "falsification_coverage": 0.60,
            "representation_coverage": 0.35,
            "error_diversity": 0.50,
            "robustness": 0.80,
            "dgp_understanding": 0.50,
        }
    )
    weights: dict[str, float] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if any(value < 0 or value > 1 for value in self.targets.values()):
            raise ValueError("preferred-state targets must be between 0 and 1")
        if any(value < 0 for value in self.weights.values()):
            raise ValueError("preferred-state weights must be non-negative")


class AblationConfig(StrictModel):
    remove: list[Literal["eig", "falsifier", "preferred-state"]] = Field(default_factory=list)

    def model_post_init(self, __context: Any) -> None:
        if len(self.remove) != len(set(self.remove)):
            raise ValueError("ablation components must be unique")


class ContaminationConfig(StrictModel):
    policy: str = "strict_historical"
    block_kaggle_discussions: bool = True
    block_kaggle_code: bool = True
    block_competition_specific_github: bool = True
    require_source_provenance: bool = True
    worker_network: str = "disabled"
    obfuscate_competition_name: bool = False
    hash_column_names: bool = False


class ExecutorConfig(StrictModel):
    # `linear_local_worker` files the real Linear ticket and runs it locally. It is a verification
    # harness for the auto-filing half of the contract, never a production executor.
    adapter: str = Field(default="local", pattern="^(local|ai_dev_control_plane|linear_local_worker|competition_repo)$")
    queue: str = "kaggle-research"
    retry_infrastructure_failures: int = Field(default=2, ge=0)
    linear_team_id: str | None = None
    linear_project_id: str | None = None
    result_root: str = ".results"
    container_image: str = "python:3.11-slim"
    dataset_mounts: list[str] = Field(default_factory=list)
    workspace: str = "."
    # ai-dev-control-plane ticket contract: it parses `workers:` to pick a worker and
    # `TARGET_REPO=` to pick the checkout, so both must match that pipeline's convention.
    worker: str = "claude:opus"
    handoff: bool = False
    target_repo: str | None = None
    # `competition_repo` only: where the competition's own results convention lives, relative to
    # target_repo. Results are read from <target_repo>/<results_subdir>/<experiment>/metrics.json.
    results_subdir: str = "results"
    # Commands a shell executor will run. The gate refuses anything else *before* selection, and
    # the designer is shown the list, so an unrunnable command is not discovered at dispatch.
    command_allowlist: list[str] = Field(default_factory=lambda: ["python", "python3", "uv", "bash"])
    linear_state_id: str | None = None


class LeaderboardConfig(StrictModel):
    """Public-leaderboard feedback policy. The private score stays sealed under every mode."""

    public_feedback: LeaderboardFeedbackMode = LeaderboardFeedbackMode.GATED_BINARY
    max_public_queries: int = Field(default=3, ge=0)
    query_ledger: str = ".state/leaderboard-queries.jsonl"
    sealed_store: str = ".sealed-scores"


class ArtifactConfig(StrictModel):
    adapter: str = "local"
    root: str = ".runs"


class StorageConfig(StrictModel):
    event_store: str = "jsonl"
    projection: str = "sqlite"
    sqlite_path: str = ".state/epistemic-loop.db"


class LlmConfig(StrictModel):
    """Proposal-stage model. ai-dev-control-plane is reached only through Linear, never as an LLM.

    `cli` shells out to an already-authenticated coding CLI, which is what makes an unattended run
    possible without provisioning a second credential; `claude` uses the API directly and needs
    `ANTHROPIC_API_KEY`; `file_bridge` puts a human in the proposal slot.
    """

    adapter: str = Field(default="cli", pattern="^(cli|claude|file_bridge)$")
    model: str = "claude-opus-5"
    max_tokens: int = Field(default=16000, ge=1024)
    effort: str = Field(default="high", pattern="^(low|medium|high|xhigh|max)$")
    structured_output_required: bool = True
    store_raw_response: bool = True
    #: `cli` adapter: which installed CLI to drive, or an explicit command overriding the preset.
    cli_preset: str = Field(default="claude", pattern="^(claude|codex)$")
    cli_command: str | None = None
    cli_timeout_seconds: float = Field(default=900, gt=0)
    cli_max_attempts: int = Field(default=3, ge=1, le=6)


class AppConfig(StrictModel):
    run: RunConfig
    competition: CompetitionConfig
    system: SystemConfig = Field(default_factory=SystemConfig)
    agents: AgentIslandConfig = Field(default_factory=AgentIslandConfig)
    communication: CommunicationConfig = Field(default_factory=CommunicationConfig)
    diversity: DiversityConfig = Field(default_factory=DiversityConfig)
    action_space: ActionSpaceConfig = Field(default_factory=ActionSpaceConfig)
    phase_gate: PhaseGateConfig = Field(default_factory=PhaseGateConfig)
    structure_discovery: StructureDiscoveryConfig = Field(default_factory=StructureDiscoveryConfig)
    archive: CandidateArchiveConfig = Field(default_factory=CandidateArchiveConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)
    budgets: Budget = Field(default_factory=Budget)
    loop: LoopConfig = Field(default_factory=LoopConfig)
    selection: SelectionConfig = Field(default_factory=SelectionConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
    qd: QDConfig = Field(default_factory=QDConfig)
    oof: OOFConfig = Field(default_factory=OOFConfig)
    calibration: CalibrationConfig = Field(default_factory=CalibrationConfig)
    preferred_state: PreferredStateConfig = Field(default_factory=PreferredStateConfig)
    ablation: AblationConfig = Field(default_factory=AblationConfig)
    holdout: HoldoutPolicy = Field(default_factory=HoldoutPolicy)
    leaderboard: LeaderboardConfig = Field(default_factory=LeaderboardConfig)
    contamination: ContaminationConfig = Field(default_factory=ContaminationConfig)
    executor: ExecutorConfig = Field(default_factory=ExecutorConfig)
    artifacts: ArtifactConfig = Field(default_factory=ArtifactConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    llm: LlmConfig = Field(default_factory=LlmConfig)
    benchmark_id: str | None = None
    synthetic_scenarios: list[str] | None = None


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("configuration root must be an object")
    return AppConfig.model_validate(_expand_env(raw))


def config_hash(config: AppConfig) -> str:
    canonical = json.dumps(config.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
