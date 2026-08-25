from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from epistemic_loop.domain.enums import LeaderboardFeedbackMode, Phase, RunMode, ValidationSplitType
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
    discovery: PhaseWeights = PhaseWeights(pragmatic=0.20, epistemic=0.45, robustness=0.20, diversity=0.15)
    consolidation: PhaseWeights = PhaseWeights(pragmatic=0.35, epistemic=0.30, robustness=0.25, diversity=0.10)
    exploitation: PhaseWeights = PhaseWeights(pragmatic=0.55, epistemic=0.15, robustness=0.25, diversity=0.05)
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


class QDConfig(StrictModel):
    maximum_archive_size: int = Field(default=100, ge=1)
    quality_floor_relative_to_best: float = Field(default=0.97, ge=0, le=1)


class OOFConfig(StrictModel):
    save_row_level_predictions: bool = True
    format: str = Field(default="parquet", pattern="^(parquet|jsonl)$")


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
