from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from epistemic_loop.domain.models import DomainModel, utc_now


class EventType(StrEnum):
    RUN_CREATED = "RunCreated"
    WORLD_MODEL_RECORDED = "WorldModelRecorded"
    VALIDATION_WORLD_REGISTERED = "ValidationWorldRegistered"
    VALIDATION_EVIDENCE_RECORDED = "ValidationEvidenceRecorded"
    VALIDATION_POSTERIOR_UPDATED = "ValidationPosteriorUpdated"
    OBSERVATION_RECORDED = "ObservationRecorded"
    HYPOTHESIS_PROPOSED = "HypothesisProposed"
    HYPOTHESIS_REVISED = "HypothesisRevised"
    EXPERIMENT_PROPOSED = "ExperimentProposed"
    EXPERIMENT_SELECTED = "ExperimentSelected"
    EXPERIMENT_STARTED = "ExperimentStarted"
    EXPERIMENT_COMPLETED = "ExperimentCompleted"
    EXPERIMENT_FAILED = "ExperimentFailed"
    EXPERIMENT_RETRY_SCHEDULED = "ExperimentRetryScheduled"
    RESOURCE_RECONCILED = "ResourceReconciled"
    AGENT_RESOURCE_RECORDED = "AgentResourceRecorded"
    FALSIFICATION_RECORDED = "FalsificationRecorded"
    FALSIFICATION_PROPOSED = "FalsificationProposed"
    BELIEF_UPDATED = "BeliefUpdated"
    FORECAST_CALIBRATION_RECORDED = "ForecastCalibrationRecorded"
    PHASE_CHANGED = "PhaseChanged"
    STATE_CHANGED = "StateChanged"
    RESEARCH_BRIEF_CREATED = "ResearchBriefCreated"
    FINAL_SELECTION_RULE_REGISTERED = "FinalSelectionRuleRegistered"
    QD_CANDIDATE_EVALUATED = "QDCandidateEvaluated"
    OOF_ARTIFACT_RECORDED = "OOFArtifactRecorded"
    OOF_ANALYSIS_RECORDED = "OOFAnalysisRecorded"
    OOF_ENSEMBLE_CREATED = "OOFEnsembleCreated"
    SUBMISSION_SEALED = "SubmissionSealed"
    LEADERBOARD_FEEDBACK_RECORDED = "LeaderboardFeedbackRecorded"
    HOLDOUT_UNSEALED = "HoldoutUnsealed"
    RUN_FINALIZED = "RunFinalized"
    VIOLATION_DETECTED = "ViolationDetected"


class EventEnvelope(DomainModel):
    event_id: str
    sequence: int = Field(ge=1)
    run_id: str
    event_type: EventType
    occurred_at: datetime = Field(default_factory=utc_now)
    payload: dict[str, Any]
    schema_version: int = Field(default=1, ge=1)
    previous_hash: str | None = None
    event_hash: str
