"""Contracts for v0.3.7 reproducibility, lineage, null, and transfer trials."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class V037ResearchMode(StrEnum):
    EXPLOIT = "exploit"
    EXPLORE = "explore"
    EPISTEMIC = "epistemic"


class LineagePolicy(StrEnum):
    DETERMINISTIC_BEST = "deterministic_best"
    POSTERIOR_COMMIT = "posterior_commit"
    TWO_HIT_MATURATION = "two_hit_maturation"


class V037Resolution(StrEnum):
    VALIDATED_ACTIONABLE_TRANSFERRED = "validated_actionable_transferred"
    VALIDATED_ACTIONABLE_NOT_TRANSFERRED = "validated_actionable_not_transferred"
    VALIDATED_NON_ACTIONABLE = "validated_non_actionable"
    USEFUL_ENCODING_UNVALIDATED = "useful_encoding_unvalidated"
    FALSIFIED = "falsified"
    INCONCLUSIVE = "inconclusive"


class NullStoppingReason(StrEnum):
    FUTILITY = "futility"
    EARLY_SUPPORT = "early_support"
    MAX_REPLICATES = "max_replicates"
    NOT_RUN = "not_run"


@dataclass(frozen=True)
class V037Confidence:
    p_structure_exists: float
    p_evidence_sufficient: float
    p_actionable: float
    p_positive_transfer: float

    def __post_init__(self) -> None:
        if any(not math.isfinite(value) or not 0 <= value <= 1 for value in self.values()):
            raise ValueError("all decomposed confidence values must lie in [0,1]")

    def values(self) -> tuple[float, float, float, float]:
        return (
            self.p_structure_exists,
            self.p_evidence_sufficient,
            self.p_actionable,
            self.p_positive_transfer,
        )


@dataclass(frozen=True)
class V037FailureTrace:
    hypothesis_generated: bool
    discriminating_test_proposed: bool
    implementation_completed: bool
    support_observed: bool
    promotion_passed: bool
    above_row_unit_considered: bool
    history_or_link_intervention_considered: bool

    @property
    def failure_stage(self) -> str:
        if not self.hypothesis_generated:
            return "hypothesis_generation"
        if not self.discriminating_test_proposed:
            return "experiment_design"
        if not self.implementation_completed:
            return "implementation"
        if not self.support_observed:
            return "evidence"
        if not self.promotion_passed:
            return "promotion"
        return "none"


@dataclass(frozen=True)
class V037ResearchDescriptor:
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
        if any(not value.strip() for value in values):
            raise ValueError("research descriptor fields must be non-empty")


@dataclass(frozen=True)
class V037Proposal:
    mode: V037ResearchMode
    lineage_id: str
    description: str
    descriptor: V037ResearchDescriptor
    expected_decision: str
    utility_mean: float
    utility_std: float
    competing_hypotheses: tuple[str, ...] = ()
    discriminating_observable: str | None = None

    def __post_init__(self) -> None:
        if not self.lineage_id.strip() or not self.description.strip() or not self.expected_decision.strip():
            raise ValueError("proposal identity, description, and decision are required")
        if self.utility_std < 0 or not all(math.isfinite(item) for item in (self.utility_mean, self.utility_std)):
            raise ValueError("proposal utility posterior must be finite")
        if self.mode is V037ResearchMode.EPISTEMIC and (
            len(self.competing_hypotheses) < 2 or not self.discriminating_observable
        ):
            raise ValueError("epistemic proposals require alternatives and an observable")


@dataclass(frozen=True)
class V037CycleRecord:
    cycle: int
    proposals: tuple[V037Proposal, ...]
    selected_lineage_id: str
    selected_mode: V037ResearchMode
    decision_changed: bool
    performance_improved: bool
    uncertainty_reduced: bool
    falsification_evidence_added: bool
    converted_to_parent_or_final: bool
    lineage_followup: bool
    lineage_explicitly_closed: bool

    def __post_init__(self) -> None:
        if not 1 <= self.cycle <= 4 or len(self.proposals) < 3:
            raise ValueError("each cycle requires three proposals and a cycle in [1,4]")
        if {item.mode for item in self.proposals} != set(V037ResearchMode):
            raise ValueError("each cycle requires exploit, explore, and epistemic proposals")
        selected = [item for item in self.proposals if item.lineage_id == self.selected_lineage_id]
        if len(selected) != 1 or selected[0].mode is not self.selected_mode:
            raise ValueError("selected lineage and mode must identify exactly one proposal")


@dataclass(frozen=True)
class FullRefitNullSummary:
    replicate_gains: tuple[float, ...]
    all_replicates_refit_features_and_model: bool
    preserved_confounders: tuple[str, ...]
    destroyed_relation: str
    stopping_reason: NullStoppingReason

    def __post_init__(self) -> None:
        if any(not math.isfinite(value) for value in self.replicate_gains):
            raise ValueError("null gains must be finite")
        count = len(self.replicate_gains)
        if self.stopping_reason is NullStoppingReason.NOT_RUN:
            if count:
                raise ValueError("not-run null cannot contain replicates")
            return
        if count < 5 or count > 30 or count % 5:
            raise ValueError("sequential full-refit null requires 5..30 replicates in blocks of five")
        if not self.destroyed_relation.strip() or not self.preserved_confounders:
            raise ValueError("executed null requires preserved confounders and destroyed relation")


@dataclass(frozen=True)
class TranslationPredictions:
    candidate_id: str
    translation_kind: str
    confirmation_predictions: tuple[float, ...]
    transfer_predictions: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.candidate_id.strip() or not self.translation_kind.strip():
            raise ValueError("translation identity and kind are required")
        values = (*self.confirmation_predictions, *self.transfer_predictions)
        if not values or any(not math.isfinite(value) or not 0 <= value <= 1 for value in values):
            raise ValueError("translation predictions must be finite probabilities")


@dataclass(frozen=True)
class V037ContextArtifact:
    opaque_context_id: str
    research_control_auc: float
    research_structure_auc: float
    independent_implication_strength: float
    control_confirmation_predictions: tuple[float, ...]
    control_transfer_predictions: tuple[float, ...]
    translations: tuple[TranslationPredictions, ...]

    def __post_init__(self) -> None:
        if not self.opaque_context_id.strip():
            raise ValueError("opaque context identity is required")
        if not all(0 <= value <= 1 for value in (self.research_control_auc, self.research_structure_auc)):
            raise ValueError("research AUC must lie in [0,1]")
        if not 0 <= self.independent_implication_strength <= 1:
            raise ValueError("independent implication must lie in [0,1]")
        if len(self.translations) < 2:
            raise ValueError("each context requires at least two downstream translations")
        if len({item.candidate_id for item in self.translations}) != len(self.translations):
            raise ValueError("translation candidate identities must be unique")
        confirmation_length = len(self.control_confirmation_predictions)
        transfer_length = len(self.control_transfer_predictions)
        if not confirmation_length or not transfer_length:
            raise ValueError("control predictions must cover both hidden regions")
        for item in self.translations:
            if len(item.confirmation_predictions) != confirmation_length:
                raise ValueError("confirmation prediction lengths must align")
            if len(item.transfer_predictions) != transfer_length:
                raise ValueError("transfer prediction lengths must align")

    @property
    def research_gain(self) -> float:
        return self.research_structure_auc - self.research_control_auc


@dataclass(frozen=True)
class V037PackSubmission:
    opaque_pack_id: str
    cycles: tuple[V037CycleRecord, ...]
    resolution: V037Resolution
    confidence: V037Confidence
    failure_trace: V037FailureTrace
    claim: str
    alternatives: tuple[str, ...]
    predicted_true: str
    predicted_false: str
    confounders: tuple[str, ...]
    falsification_conditions: tuple[str, ...]
    independent_implication: str
    affected_decisions: tuple[str, ...]
    causal_safety_passed: bool
    leave_one_context_out_stable: bool
    null_summary: FullRefitNullSummary
    selected_translation_id: str
    shadow_candidate_ids: tuple[str, ...]
    contexts: tuple[V037ContextArtifact, ...]

    def __post_init__(self) -> None:
        if not self.opaque_pack_id.strip() or not self.claim.strip() or not self.selected_translation_id.strip():
            raise ValueError("pack, claim, and selected translation identities are required")
        if not 1 <= len(self.cycles) <= 4 or tuple(item.cycle for item in self.cycles) != tuple(
            range(1, len(self.cycles) + 1)
        ):
            raise ValueError("cycles must be consecutive and limited to four")
        if len(self.contexts) < 3 or len({item.opaque_context_id for item in self.contexts}) != len(self.contexts):
            raise ValueError("aggregate evaluation requires three unique contexts")
        promoted = self.resolution in {
            V037Resolution.VALIDATED_ACTIONABLE_TRANSFERRED,
            V037Resolution.VALIDATED_ACTIONABLE_NOT_TRANSFERRED,
            V037Resolution.VALIDATED_NON_ACTIONABLE,
        }
        resolved = promoted or self.resolution is V037Resolution.FALSIFIED
        if promoted and (len(self.alternatives) < 2 or not self.falsification_conditions):
            raise ValueError("promotion requires alternatives and falsification conditions")
        if resolved and (
            not self.null_summary.all_replicates_refit_features_and_model
            or len(self.null_summary.replicate_gains) < 5
            or not self.causal_safety_passed
        ):
            raise ValueError("terminal structural decisions require a causal-safe full-refit null")
        if any(
            self.selected_translation_id not in {item.candidate_id for item in context.translations}
            for context in self.contexts
        ):
            raise ValueError("selected translation must exist in every context artifact")


@dataclass(frozen=True)
class V037AgentSubmission:
    version: str
    suite_id: str
    run_id: str
    agent_id: str
    sampling_seed: int
    prompt_arm: str
    lineage_policy: LineagePolicy
    prompt_hash: str
    policy_contract_hash: str
    human_assisted: bool
    cross_run_information_used: bool
    artifact_complete: bool
    oof_honesty_passed: bool
    hidden_isolation_passed: bool
    packs: tuple[V037PackSubmission, ...]

    def __post_init__(self) -> None:
        if self.version != "0.3.7" or not self.suite_id.strip() or not self.run_id.strip():
            raise ValueError("invalid v0.3.7 submission identity")
        if not self.packs or not self.prompt_hash.strip() or not self.policy_contract_hash.strip():
            raise ValueError("v0.3.7 submission requires packs and frozen policy hashes")


@dataclass(frozen=True)
class V037SubmissionValidation:
    valid: bool
    errors: tuple[str, ...]


def load_v037_submission(path: Path) -> V037AgentSubmission:
    payload = json.loads(path.read_text())
    packs: list[V037PackSubmission] = []
    for pack in payload["packs"]:
        cycles: list[V037CycleRecord] = []
        for cycle in pack["cycles"]:
            proposals = tuple(
                V037Proposal(
                    mode=V037ResearchMode(item["mode"]),
                    lineage_id=str(item["lineage_id"]),
                    description=str(item["description"]),
                    descriptor=V037ResearchDescriptor(**item["descriptor"]),
                    expected_decision=str(item["expected_decision"]),
                    utility_mean=float(item["utility_mean"]),
                    utility_std=float(item["utility_std"]),
                    competing_hypotheses=tuple(item.get("competing_hypotheses", ())),
                    discriminating_observable=item.get("discriminating_observable"),
                )
                for item in cycle["proposals"]
            )
            cycles.append(
                V037CycleRecord(
                    cycle=int(cycle["cycle"]),
                    proposals=proposals,
                    selected_lineage_id=str(cycle["selected_lineage_id"]),
                    selected_mode=V037ResearchMode(cycle["selected_mode"]),
                    decision_changed=bool(cycle["decision_changed"]),
                    performance_improved=bool(cycle["performance_improved"]),
                    uncertainty_reduced=bool(cycle["uncertainty_reduced"]),
                    falsification_evidence_added=bool(cycle["falsification_evidence_added"]),
                    converted_to_parent_or_final=bool(cycle["converted_to_parent_or_final"]),
                    lineage_followup=bool(cycle["lineage_followup"]),
                    lineage_explicitly_closed=bool(cycle["lineage_explicitly_closed"]),
                )
            )
        contexts = tuple(
            V037ContextArtifact(
                opaque_context_id=str(context["opaque_context_id"]),
                research_control_auc=float(context["research_control_auc"]),
                research_structure_auc=float(context["research_structure_auc"]),
                independent_implication_strength=float(context["independent_implication_strength"]),
                control_confirmation_predictions=tuple(
                    float(value) for value in context["control_confirmation_predictions"]
                ),
                control_transfer_predictions=tuple(float(value) for value in context["control_transfer_predictions"]),
                translations=tuple(
                    TranslationPredictions(
                        candidate_id=str(item["candidate_id"]),
                        translation_kind=str(item["translation_kind"]),
                        confirmation_predictions=tuple(float(value) for value in item["confirmation_predictions"]),
                        transfer_predictions=tuple(float(value) for value in item["transfer_predictions"]),
                    )
                    for item in context["translations"]
                ),
            )
            for context in pack["contexts"]
        )
        null = pack["null_summary"]
        packs.append(
            V037PackSubmission(
                opaque_pack_id=str(pack["opaque_pack_id"]),
                cycles=tuple(cycles),
                resolution=V037Resolution(pack["resolution"]),
                confidence=V037Confidence(**pack["confidence"]),
                failure_trace=V037FailureTrace(**pack["failure_trace"]),
                claim=str(pack["claim"]),
                alternatives=tuple(pack["alternatives"]),
                predicted_true=str(pack["predicted_true"]),
                predicted_false=str(pack["predicted_false"]),
                confounders=tuple(pack["confounders"]),
                falsification_conditions=tuple(pack["falsification_conditions"]),
                independent_implication=str(pack["independent_implication"]),
                affected_decisions=tuple(pack["affected_decisions"]),
                causal_safety_passed=bool(pack["causal_safety_passed"]),
                leave_one_context_out_stable=bool(pack["leave_one_context_out_stable"]),
                null_summary=FullRefitNullSummary(
                    replicate_gains=tuple(float(value) for value in null["replicate_gains"]),
                    all_replicates_refit_features_and_model=bool(null["all_replicates_refit_features_and_model"]),
                    preserved_confounders=tuple(null["preserved_confounders"]),
                    destroyed_relation=str(null["destroyed_relation"]),
                    stopping_reason=NullStoppingReason(null["stopping_reason"]),
                ),
                selected_translation_id=str(pack["selected_translation_id"]),
                shadow_candidate_ids=tuple(pack["shadow_candidate_ids"]),
                contexts=contexts,
            )
        )
    return V037AgentSubmission(
        version=str(payload["version"]),
        suite_id=str(payload["suite_id"]),
        run_id=str(payload["run_id"]),
        agent_id=str(payload["agent_id"]),
        sampling_seed=int(payload["sampling_seed"]),
        prompt_arm=str(payload["prompt_arm"]),
        lineage_policy=LineagePolicy(payload["lineage_policy"]),
        prompt_hash=str(payload["prompt_hash"]),
        policy_contract_hash=str(payload["policy_contract_hash"]),
        human_assisted=bool(payload["human_assisted"]),
        cross_run_information_used=bool(payload["cross_run_information_used"]),
        artifact_complete=bool(payload["artifact_complete"]),
        oof_honesty_passed=bool(payload["oof_honesty_passed"]),
        hidden_isolation_passed=bool(payload["hidden_isolation_passed"]),
        packs=tuple(packs),
    )


def validate_v037_submission(submission: V037AgentSubmission, packet: dict[str, Any]) -> V037SubmissionValidation:
    errors: list[str] = []
    identity_fields = (
        "suite_id",
        "run_id",
        "agent_id",
        "sampling_seed",
        "prompt_arm",
        "prompt_hash",
        "policy_contract_hash",
    )
    for field in identity_fields:
        if getattr(submission, field) != packet.get(field):
            errors.append(f"{field} mismatch")
    if submission.lineage_policy.value != packet.get("lineage_policy"):
        errors.append("lineage_policy mismatch")
    expected_packs = {str(item["opaque_pack_id"]): item for item in packet.get("packs", ())}
    actual_packs = {item.opaque_pack_id: item for item in submission.packs}
    if set(actual_packs) != set(expected_packs):
        errors.append("pack set mismatch")
    for pack_id, pack in actual_packs.items():
        if pack_id not in expected_packs:
            continue
        expected_contexts = {str(item["opaque_context_id"]): item for item in expected_packs[pack_id]["contexts"]}
        actual_contexts = {item.opaque_context_id: item for item in pack.contexts}
        if set(actual_contexts) != set(expected_contexts):
            errors.append(f"{pack_id}: context set mismatch")
            continue
        for context_id, context in actual_contexts.items():
            expected = expected_contexts[context_id]
            if len(context.control_confirmation_predictions) != int(expected["confirmation_rows"]):
                errors.append(f"{pack_id}/{context_id}: confirmation row-count mismatch")
            if len(context.control_transfer_predictions) != int(expected["transfer_rows"]):
                errors.append(f"{pack_id}/{context_id}: transfer row-count mismatch")
    if submission.human_assisted:
        errors.append("human-assisted primary run")
    if submission.cross_run_information_used:
        errors.append("cross-run information used")
    if not submission.artifact_complete:
        errors.append("artifact contract incomplete")
    if not submission.oof_honesty_passed:
        errors.append("OOF honesty failed")
    if not submission.hidden_isolation_passed:
        errors.append("hidden isolation failed")
    return V037SubmissionValidation(not errors, tuple(errors))


def v037_submission_contract() -> dict[str, Any]:
    """Return the complete agent-visible contract without controller truth."""

    return {
        "version": "0.3.7",
        "top_level_fields": [
            "version",
            "suite_id",
            "run_id",
            "agent_id",
            "sampling_seed",
            "prompt_arm",
            "lineage_policy",
            "prompt_hash",
            "policy_contract_hash",
            "human_assisted",
            "cross_run_information_used",
            "artifact_complete",
            "oof_honesty_passed",
            "hidden_isolation_passed",
            "packs",
        ],
        "resolution_values": [item.value for item in V037Resolution],
        "research_modes": [item.value for item in V037ResearchMode],
        "lineage_policies": [item.value for item in LineagePolicy],
        "pack_fields": {
            "opaque_pack_id": "string from agent_packet.json",
            "cycles": "one to four complete cycle objects",
            "resolution": "one resolution_values entry",
            "confidence": "object containing every confidence_fields entry",
            "failure_trace": "object containing every failure_trace_fields entry",
            "claim": "non-empty free text",
            "alternatives": "list with at least two items for a promoted structure",
            "predicted_true": "observable prediction under the claim",
            "predicted_false": "observable prediction under an alternative",
            "confounders": "list of considered confounders",
            "falsification_conditions": "preregistered rejection criteria",
            "independent_implication": "non-AUC implication",
            "affected_decisions": "downstream decision list",
            "causal_safety_passed": "boolean",
            "leave_one_context_out_stable": "boolean",
            "null_summary": "object matching null_summary",
            "selected_translation_id": "candidate id present in every context",
            "shadow_candidate_ids": "retained non-selected candidates",
            "contexts": "one complete context object per packet context",
        },
        "confidence_fields": {
            "p_structure_exists": "probability in [0,1]",
            "p_evidence_sufficient": "probability in [0,1]",
            "p_actionable": "probability in [0,1]",
            "p_positive_transfer": "probability in [0,1]",
        },
        "failure_trace_fields": {
            "hypothesis_generated": "boolean",
            "discriminating_test_proposed": "boolean",
            "implementation_completed": "boolean",
            "support_observed": "boolean",
            "promotion_passed": "boolean",
            "above_row_unit_considered": "boolean",
            "history_or_link_intervention_considered": "boolean",
        },
        "null_summary": {
            "replicate_gains": "5..30 values in blocks of five, empty only when not_run",
            "all_replicates_refit_features_and_model": "boolean",
            "preserved_confounders": "non-empty list for an executed null",
            "destroyed_relation": "free text",
            "stopping_reason": [item.value for item in NullStoppingReason],
        },
        "cycle_fields": {
            "cycle": "consecutive integer 1..4",
            "proposals": "at least three proposal objects covering all research_modes",
            "selected_lineage_id": "exactly one lineage_id in proposals",
            "selected_mode": "mode of selected lineage",
            "decision_changed": "boolean",
            "performance_improved": "boolean",
            "uncertainty_reduced": "boolean",
            "falsification_evidence_added": "boolean",
            "converted_to_parent_or_final": "boolean",
            "lineage_followup": "boolean",
            "lineage_explicitly_closed": "boolean",
        },
        "proposal_fields": {
            "mode": "one research_modes entry",
            "lineage_id": "non-empty string",
            "description": "non-empty free text",
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
            "utility_mean": "finite number",
            "utility_std": "finite non-negative number",
            "competing_hypotheses": "two or more strings for epistemic mode; otherwise list",
            "discriminating_observable": "non-empty string for epistemic mode; otherwise null allowed",
        },
        "context_fields": {
            "opaque_context_id": "string from packet",
            "research_control_auc": "research-only AUC in [0,1]",
            "research_structure_auc": "research-only AUC in [0,1]",
            "independent_implication_strength": "research-only value in [0,1]",
            "control_confirmation_predictions": "aligned probability list in confirmation file order",
            "control_transfer_predictions": "aligned probability list in transfer file order",
            "translations": "at least two translation objects",
        },
        "translation_fields": {
            "candidate_id": "same candidate id must be used across contexts",
            "translation_kind": "non-empty free text",
            "confirmation_predictions": "aligned probability list in confirmation file order",
            "transfer_predictions": "aligned probability list in transfer file order",
        },
        "lock_rule": "all runs and both hidden-region predictions are locked before controller evaluation",
    }
