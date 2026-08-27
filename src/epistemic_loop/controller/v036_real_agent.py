"""Contracts for blind real-agent research and post-freeze communication."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class V036ResearchMode(StrEnum):
    EXPLOIT = "exploit"
    EXPLORE = "explore"
    EPISTEMIC = "epistemic"


class StructureResolution(StrEnum):
    VALIDATED_ACTIONABLE = "validated_actionable"
    VALIDATED_NON_ACTIONABLE = "validated_non_actionable"
    USEFUL_ENCODING_UNVALIDATED = "useful_encoding_unvalidated"
    FALSIFIED = "falsified"
    INCONCLUSIVE = "inconclusive"


class CommunicationMode(StrEnum):
    INDEPENDENT = "independent"
    EVIDENCE = "evidence"
    DEBT = "debt"
    CANDIDATE = "candidate"
    FULL = "full"


@dataclass(frozen=True)
class V036ResearchDescriptor:
    hypothesis_family: str
    representation_family: str
    validation_world: str
    observation_unit: str
    data_slice: str
    experiment_operator: str
    model_family: str
    downstream_decision: str
    structural_claim: bool

    def __post_init__(self) -> None:
        values = (
            self.hypothesis_family,
            self.representation_family,
            self.validation_world,
            self.observation_unit,
            self.data_slice,
            self.experiment_operator,
            self.model_family,
            self.downstream_decision,
        )
        if any(not item.strip() for item in values):
            raise ValueError("research descriptor fields must be non-empty")


@dataclass(frozen=True)
class V036Proposal:
    mode: V036ResearchMode
    description: str
    descriptor: V036ResearchDescriptor
    expected_decision: str
    competing_hypotheses: tuple[str, ...] = ()
    discriminating_observable: str | None = None

    def __post_init__(self) -> None:
        if not self.description.strip() or not self.expected_decision.strip():
            raise ValueError("proposal description and expected decision are required")
        if self.mode is V036ResearchMode.EPISTEMIC and (
            len(self.competing_hypotheses) < 2 or not self.discriminating_observable
        ):
            raise ValueError("epistemic proposals require competing hypotheses and an observable")


@dataclass(frozen=True)
class V036CycleRecord:
    cycle: int
    proposals: tuple[V036Proposal, ...]
    selected_mode: V036ResearchMode
    selected_description: str
    decision_changed: bool
    performance_improved: bool
    uncertainty_reduced: bool
    falsification_evidence_added: bool
    converted_to_parent_or_final: bool

    def __post_init__(self) -> None:
        if not 1 <= self.cycle <= 4:
            raise ValueError("v0.3.6 cycles must lie in [1, 4]")
        if len(self.proposals) < 3:
            raise ValueError("each real-agent cycle requires at least three proposals")
        modes = {item.mode for item in self.proposals}
        if modes != set(V036ResearchMode):
            raise ValueError("each cycle requires exploit, explore, and epistemic proposals")
        if self.selected_mode not in modes or not self.selected_description.strip():
            raise ValueError("selected proposal must be recorded")


@dataclass(frozen=True)
class ContextPredictionArtifact:
    opaque_context_id: str
    research_control_auc: float
    research_structure_auc: float
    null_gain_95th_percentile: float
    independent_implication_strength: float
    control_predictions: tuple[float, ...]
    structure_predictions: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.opaque_context_id.strip():
            raise ValueError("opaque context identity is required")
        if not 0 <= self.research_control_auc <= 1 or not 0 <= self.research_structure_auc <= 1:
            raise ValueError("research AUC values must lie in [0, 1]")
        if not 0 <= self.independent_implication_strength <= 1:
            raise ValueError("implication strength must lie in [0, 1]")
        if len(self.control_predictions) != len(self.structure_predictions) or not self.control_predictions:
            raise ValueError("sealed prediction vectors must be non-empty and aligned")
        probabilities = (*self.control_predictions, *self.structure_predictions)
        if any(not math.isfinite(item) or not 0 <= item <= 1 for item in probabilities):
            raise ValueError("sealed predictions must be finite probabilities")

    @property
    def research_gain(self) -> float:
        return self.research_structure_auc - self.research_control_auc


@dataclass(frozen=True)
class PackResearchSubmission:
    opaque_pack_id: str
    cycles: tuple[V036CycleRecord, ...]
    resolution: StructureResolution
    confidence: float
    claim: str
    alternatives: tuple[str, ...]
    predicted_true: str
    predicted_false: str
    confounders: tuple[str, ...]
    falsification_conditions: tuple[str, ...]
    independent_implication: str
    affected_decisions: tuple[str, ...]
    matched_null_executed: bool
    causal_safety_passed: bool
    leave_one_context_out_stable: bool
    selected_candidate_id: str
    shadow_candidate_ids: tuple[str, ...]
    contexts: tuple[ContextPredictionArtifact, ...]

    def __post_init__(self) -> None:
        if not self.opaque_pack_id.strip() or not self.claim.strip() or not self.selected_candidate_id.strip():
            raise ValueError("pack identity, claim, and selected candidate are required")
        if not 0 <= self.confidence <= 1:
            raise ValueError("structure confidence must lie in [0, 1]")
        if len(self.cycles) > 4 or not self.cycles:
            raise ValueError("a pack requires between one and four adaptive cycles")
        if tuple(item.cycle for item in self.cycles) != tuple(range(1, len(self.cycles) + 1)):
            raise ValueError("cycle numbers must be consecutive")
        if len(self.contexts) < 3 or len({item.opaque_context_id for item in self.contexts}) != len(self.contexts):
            raise ValueError("aggregate-only promotion requires three unique contexts")
        structural = self.resolution in {
            StructureResolution.VALIDATED_ACTIONABLE,
            StructureResolution.VALIDATED_NON_ACTIONABLE,
        }
        if structural and (len(self.alternatives) < 2 or not self.falsification_conditions):
            raise ValueError("validated structures require alternatives and falsification conditions")
        if structural and (not self.matched_null_executed or not self.causal_safety_passed):
            raise ValueError("validated structures require null and causal-safety evidence")


@dataclass(frozen=True)
class RealAgentSubmission:
    version: str
    suite_id: str
    agent_id: str
    prompt_hash: str
    human_assisted: bool
    cross_agent_information_used: bool
    artifact_complete: bool
    oof_honesty_passed: bool
    sealed_isolation_passed: bool
    packs: tuple[PackResearchSubmission, ...]

    def __post_init__(self) -> None:
        if self.version != "0.3.6" or not self.suite_id.strip() or not self.agent_id.strip():
            raise ValueError("v0.3.6 submission identity is invalid")
        if not self.prompt_hash.strip() or not self.packs:
            raise ValueError("prompt hash and pack submissions are required")


@dataclass(frozen=True)
class SubmissionValidation:
    valid: bool
    errors: tuple[str, ...]


@dataclass(frozen=True)
class MigrationPacket:
    mode: CommunicationMode
    source_agent: str
    target_agent: str
    evidence: tuple[str, ...] = ()
    unresolved_questions: tuple[str, ...] = ()
    candidate_refs: tuple[str, ...] = ()
    hypotheses: tuple[str, ...] = ()
    scores: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if self.source_agent == self.target_agent:
            raise ValueError("migration requires different source and target agents")
        if self.mode is CommunicationMode.INDEPENDENT and any(
            (self.evidence, self.unresolved_questions, self.candidate_refs, self.hypotheses, self.scores)
        ):
            raise ValueError("independent mode cannot carry cross-agent information")
        if self.mode is CommunicationMode.EVIDENCE and any(
            (self.unresolved_questions, self.candidate_refs, self.hypotheses, self.scores)
        ):
            raise ValueError("evidence mode may carry reproduced observations only")
        if self.mode is CommunicationMode.DEBT and any((self.candidate_refs, self.hypotheses, self.scores)):
            raise ValueError("debt mode may carry evidence and unresolved questions only")
        if self.mode is CommunicationMode.CANDIDATE and any((self.hypotheses, self.scores)):
            raise ValueError("candidate migration must not reveal beliefs or score ranking")


def load_real_agent_submission(path: Path) -> RealAgentSubmission:
    payload = json.loads(path.read_text())
    packs: list[PackResearchSubmission] = []
    for pack in payload["packs"]:
        cycles: list[V036CycleRecord] = []
        for cycle in pack["cycles"]:
            proposals = tuple(
                V036Proposal(
                    mode=V036ResearchMode(item["mode"]),
                    description=str(item["description"]),
                    descriptor=V036ResearchDescriptor(**item["descriptor"]),
                    expected_decision=str(item["expected_decision"]),
                    competing_hypotheses=tuple(item.get("competing_hypotheses", ())),
                    discriminating_observable=item.get("discriminating_observable"),
                )
                for item in cycle["proposals"]
            )
            cycles.append(
                V036CycleRecord(
                    cycle=int(cycle["cycle"]),
                    proposals=proposals,
                    selected_mode=V036ResearchMode(cycle["selected_mode"]),
                    selected_description=str(cycle["selected_description"]),
                    decision_changed=bool(cycle["decision_changed"]),
                    performance_improved=bool(cycle["performance_improved"]),
                    uncertainty_reduced=bool(cycle["uncertainty_reduced"]),
                    falsification_evidence_added=bool(cycle["falsification_evidence_added"]),
                    converted_to_parent_or_final=bool(cycle["converted_to_parent_or_final"]),
                )
            )
        contexts = tuple(
            ContextPredictionArtifact(
                opaque_context_id=str(item["opaque_context_id"]),
                research_control_auc=float(item["research_control_auc"]),
                research_structure_auc=float(item["research_structure_auc"]),
                null_gain_95th_percentile=float(item["null_gain_95th_percentile"]),
                independent_implication_strength=float(item["independent_implication_strength"]),
                control_predictions=tuple(float(value) for value in item["control_predictions"]),
                structure_predictions=tuple(float(value) for value in item["structure_predictions"]),
            )
            for item in pack["contexts"]
        )
        packs.append(
            PackResearchSubmission(
                opaque_pack_id=str(pack["opaque_pack_id"]),
                cycles=tuple(cycles),
                resolution=StructureResolution(pack["resolution"]),
                confidence=float(pack["confidence"]),
                claim=str(pack["claim"]),
                alternatives=tuple(pack["alternatives"]),
                predicted_true=str(pack["predicted_true"]),
                predicted_false=str(pack["predicted_false"]),
                confounders=tuple(pack["confounders"]),
                falsification_conditions=tuple(pack["falsification_conditions"]),
                independent_implication=str(pack["independent_implication"]),
                affected_decisions=tuple(pack["affected_decisions"]),
                matched_null_executed=bool(pack["matched_null_executed"]),
                causal_safety_passed=bool(pack["causal_safety_passed"]),
                leave_one_context_out_stable=bool(pack["leave_one_context_out_stable"]),
                selected_candidate_id=str(pack["selected_candidate_id"]),
                shadow_candidate_ids=tuple(pack["shadow_candidate_ids"]),
                contexts=contexts,
            )
        )
    return RealAgentSubmission(
        version=str(payload["version"]),
        suite_id=str(payload["suite_id"]),
        agent_id=str(payload["agent_id"]),
        prompt_hash=str(payload["prompt_hash"]),
        human_assisted=bool(payload["human_assisted"]),
        cross_agent_information_used=bool(payload["cross_agent_information_used"]),
        artifact_complete=bool(payload["artifact_complete"]),
        oof_honesty_passed=bool(payload["oof_honesty_passed"]),
        sealed_isolation_passed=bool(payload["sealed_isolation_passed"]),
        packs=tuple(packs),
    )


def validate_submission_against_packet(
    submission: RealAgentSubmission,
    packet: Mapping[str, Any],
) -> SubmissionValidation:
    errors: list[str] = []
    if submission.suite_id != packet.get("suite_id"):
        errors.append("suite_id mismatch")
    if submission.agent_id != packet.get("agent_id"):
        errors.append("agent_id mismatch")
    expected_packs = {str(item["opaque_pack_id"]): item for item in packet.get("packs", ())}
    actual_packs = {item.opaque_pack_id: item for item in submission.packs}
    if set(actual_packs) != set(expected_packs):
        errors.append("pack set mismatch")
    for pack_id, pack in actual_packs.items():
        if pack_id not in expected_packs:
            continue
        expected_contexts = {
            str(item["opaque_context_id"]): int(item["sealed_rows"]) for item in expected_packs[pack_id]["contexts"]
        }
        actual_contexts = {item.opaque_context_id: item for item in pack.contexts}
        if set(actual_contexts) != set(expected_contexts):
            errors.append(f"{pack_id}: context set mismatch")
            continue
        for context_id, length in expected_contexts.items():
            artifact = actual_contexts[context_id]
            if len(artifact.control_predictions) != length or len(artifact.structure_predictions) != length:
                errors.append(f"{pack_id}/{context_id}: sealed row-count mismatch")
    if submission.human_assisted:
        errors.append("human-assisted primary run")
    if submission.cross_agent_information_used:
        errors.append("cross-agent information used in Phase 1")
    if not submission.artifact_complete:
        errors.append("artifact contract incomplete")
    if not submission.oof_honesty_passed:
        errors.append("OOF honesty failed")
    if not submission.sealed_isolation_passed:
        errors.append("sealed isolation failed")
    return SubmissionValidation(not errors, tuple(errors))


def submission_contract() -> dict[str, Any]:
    """Return the stable agent-visible JSON contract description."""

    return {
        "required_top_level": [
            "version",
            "suite_id",
            "agent_id",
            "prompt_hash",
            "human_assisted",
            "cross_agent_information_used",
            "artifact_complete",
            "oof_honesty_passed",
            "sealed_isolation_passed",
            "packs",
        ],
        "resolution_values": [item.value for item in StructureResolution],
        "cycle_modes": [item.value for item in V036ResearchMode],
        "maximum_cycles_per_pack": 4,
        "minimum_contexts_per_pack": 3,
        "prediction_requirement": "one aligned control and structure probability per sealed row",
        "pack_fields": {
            "opaque_pack_id": "string from agent_packet.json",
            "cycles": "one to four cycle records",
            "resolution": "one resolution_values entry",
            "confidence": "probability in [0,1] that a high-leverage structure exists",
            "claim": "free text",
            "alternatives": "at least two competing explanations",
            "predicted_true": "observable prediction when claim is true",
            "predicted_false": "observable prediction when claim is false",
            "confounders": "list of preserved or tested confounders",
            "falsification_conditions": "preregistered rejection conditions",
            "independent_implication": "evidence not identical to predictive AUC gain",
            "affected_decisions": "list of downstream decisions",
            "matched_null_executed": "boolean",
            "causal_safety_passed": "boolean",
            "leave_one_context_out_stable": "boolean",
            "selected_candidate_id": "local final candidate",
            "shadow_candidate_ids": "retained rejected candidates",
            "contexts": "one context prediction record per packet context",
        },
        "cycle_fields": {
            "cycle": "consecutive integer from 1",
            "proposals": "three or more proposal records covering all cycle_modes",
            "selected_mode": "one cycle_modes entry",
            "selected_description": "executed primary bundle",
            "decision_changed": "boolean",
            "performance_improved": "boolean",
            "uncertainty_reduced": "boolean",
            "falsification_evidence_added": "boolean",
            "converted_to_parent_or_final": "boolean",
        },
        "proposal_fields": {
            "mode": "exploit, explore, or epistemic",
            "description": "free text",
            "descriptor": {
                "hypothesis_family": "free text",
                "representation_family": "free text",
                "validation_world": "free text",
                "observation_unit": "free text",
                "data_slice": "free text",
                "experiment_operator": "free text",
                "model_family": "free text",
                "downstream_decision": "free text",
                "structural_claim": "boolean",
            },
            "expected_decision": "free text",
            "competing_hypotheses": "two or more strings for epistemic proposals; otherwise empty list",
            "discriminating_observable": "string for epistemic proposals; otherwise null",
        },
        "context_fields": {
            "opaque_context_id": "string from packet",
            "research_control_auc": "research-only AUC",
            "research_structure_auc": "research-only AUC",
            "null_gain_95th_percentile": "research-only matched-null gain threshold",
            "independent_implication_strength": "normalized [0,1] evidence strength",
            "control_predictions": "sealed probability vector in input row order",
            "structure_predictions": "sealed probability vector in input row order",
        },
        "primary_run_prohibitions": [
            "controller truth access",
            "sealed label access",
            "reference probe access",
            "cross-agent information",
            "human hypothesis or code assistance",
        ],
    }
