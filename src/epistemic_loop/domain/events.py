from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from epistemic_loop.domain.models import DomainModel, utc_now


class EventType(StrEnum):
    RUN_CREATED = "RunCreated"
    WORLD_MODEL_RECORDED = "WorldModelRecorded"
    OBSERVATION_RECORDED = "ObservationRecorded"
    HYPOTHESIS_PROPOSED = "HypothesisProposed"
    HYPOTHESIS_REVISED = "HypothesisRevised"
    EXPERIMENT_PROPOSED = "ExperimentProposed"
    EXPERIMENT_SELECTED = "ExperimentSelected"
    EXPERIMENT_STARTED = "ExperimentStarted"
    EXPERIMENT_COMPLETED = "ExperimentCompleted"
    EXPERIMENT_FAILED = "ExperimentFailed"
    FALSIFICATION_RECORDED = "FalsificationRecorded"
    BELIEF_UPDATED = "BeliefUpdated"
    PHASE_CHANGED = "PhaseChanged"
    STATE_CHANGED = "StateChanged"
    RESEARCH_BRIEF_CREATED = "ResearchBriefCreated"
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
