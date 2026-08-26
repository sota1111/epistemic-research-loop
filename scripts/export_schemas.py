from __future__ import annotations

import json
from pathlib import Path

from epistemic_loop.domain.events import EventEnvelope
from epistemic_loop.domain.models import (
    AgentBeliefState,
    AgentResourceRecord,
    CalibrationSummary,
    CandidateArtifactRecord,
    CandidateArtifactValidation,
    CollapseMetrics,
    CommunicationPolicy,
    DecisionBinding,
    ExperimentManifest,
    ExperimentProposal,
    ExperimentRequest,
    ExperimentResult,
    ExperimentRetryRecord,
    FinalSelectionRule,
    FoldAssignment,
    ForecastCalibrationRecord,
    GlobalControlState,
    GlobalEvidence,
    Hypothesis,
    Observation,
    OOFArtifact,
    OOFEnsemble,
    OOFRecord,
    QDCandidate,
    ResearchBrief,
    ResearchStateSnapshot,
    ResourceEstimate,
    ResourceReconciliation,
    SemanticExperimentSignature,
    ValidationWorld,
    ValidationWorldEvidence,
)

SCHEMAS = {
    "hypothesis.schema.json": Hypothesis,
    "experiment.schema.json": ExperimentProposal,
    "experiment_manifest.schema.json": ExperimentManifest,
    "experiment_request.schema.json": ExperimentRequest,
    "experiment_result.schema.json": ExperimentResult,
    "experiment_retry_record.schema.json": ExperimentRetryRecord,
    "observation.schema.json": Observation,
    "research_brief.schema.json": ResearchBrief,
    "event.schema.json": EventEnvelope,
    "validation_world.schema.json": ValidationWorld,
    "validation_world_evidence.schema.json": ValidationWorldEvidence,
    "candidate.schema.json": QDCandidate,
    "oof_record.schema.json": OOFRecord,
    "oof_artifact.schema.json": OOFArtifact,
    "oof_ensemble.schema.json": OOFEnsemble,
    "research_state.schema.json": ResearchStateSnapshot,
    "fold_assignment.schema.json": FoldAssignment,
    "forecast_calibration.schema.json": ForecastCalibrationRecord,
    "calibration_summary.schema.json": CalibrationSummary,
    "resource_reconciliation.schema.json": ResourceReconciliation,
    "final_selection_rule.schema.json": FinalSelectionRule,
    "agent_resource_record.schema.json": AgentResourceRecord,
    "agent_belief_state.schema.json": AgentBeliefState,
    "global_control_state.schema.json": GlobalControlState,
    "global_evidence.schema.json": GlobalEvidence,
    "communication_policy.schema.json": CommunicationPolicy,
    "semantic_experiment_signature.schema.json": SemanticExperimentSignature,
    "decision_binding.schema.json": DecisionBinding,
    "resource_estimate.schema.json": ResourceEstimate,
    "collapse_metrics.schema.json": CollapseMetrics,
    "candidate_artifact_record.schema.json": CandidateArtifactRecord,
    "candidate_artifact_validation.schema.json": CandidateArtifactValidation,
}


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "schemas"
    root.mkdir(parents=True, exist_ok=True)
    for name, model in SCHEMAS.items():
        (root / name).write_text(
            json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
