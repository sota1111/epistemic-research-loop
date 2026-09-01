"""Agent-submission contract for v0.4.3-c regression suites (e.g. Rossmann).

``v037_agent.py`` hard-validates two things that are wrong for a continuous target (see
docs/verification/v043_rossmann_regression_preregistration.md SS0):

- ``TranslationPredictions`` requires every prediction in ``[0,1]`` ("must be finite
  probabilities").
- ``V037ContextArtifact`` requires the agent's self-reported ``research_control_auc`` /
  ``research_structure_auc`` in ``[0,1]``.

Rather than relax those checks in place -- which would weaken the already-qualified
classification pipeline (IEEE-CIS, Santander) for every future run -- this module defines
regression-appropriate replacements for exactly those two classes and leaves
``v037_agent.py`` untouched. Everything else (cycle/lineage/null-provenance machinery,
submission-set validation, which never inspects prediction values or AUC fields) is
reused directly from ``v037_agent``.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from epistemic_loop.controller.v037_agent import (
    FullRefitNullSummary,
    LineagePolicy,
    NullStoppingReason,
    V037Confidence,
    V037CycleRecord,
    V037FailureTrace,
    V037PackSubmission,
    V037Proposal,
    V037ResearchDescriptor,
    V037ResearchMode,
    V037Resolution,
    validate_v037_submission,
)

REGRESSION_SUBMISSION_VERSION = "0.4.3"

#: Re-exported unchanged: this validator never inspects prediction values or AUC/stat
#: fields (only identity fields, pack/context set membership, row counts, and honesty
#: booleans), so it applies to a regression submission exactly as-is.
validate_v043_regression_submission = validate_v037_submission


@dataclass(frozen=True)
class V043RegressionSubmission:
    """Same shape as ``v037_agent.V037AgentSubmission``, with the ``version`` check
    relaxed to accept :data:`REGRESSION_SUBMISSION_VERSION` instead of a hardcoded
    ``"0.3.7"``. Everything else about the identity/packs shape is unchanged."""

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
        if self.version != REGRESSION_SUBMISSION_VERSION or not self.suite_id.strip() or not self.run_id.strip():
            raise ValueError("invalid v0.4.3 regression submission identity")
        if not self.packs or not self.prompt_hash.strip() or not self.policy_contract_hash.strip():
            raise ValueError("v0.4.3 regression submission requires packs and frozen policy hashes")


@dataclass(frozen=True)
class RegressionTranslationPredictions:
    candidate_id: str
    translation_kind: str
    confirmation_predictions: tuple[float, ...]
    transfer_predictions: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.candidate_id.strip() or not self.translation_kind.strip():
            raise ValueError("translation identity and kind are required")
        values = (*self.confirmation_predictions, *self.transfer_predictions)
        if not values or any(not math.isfinite(value) for value in values):
            raise ValueError("translation predictions must be finite, target-scale values")


@dataclass(frozen=True)
class RegressionContextArtifact:
    opaque_context_id: str
    research_control_stat: float
    research_structure_stat: float
    independent_implication_strength: float
    control_confirmation_predictions: tuple[float, ...]
    control_transfer_predictions: tuple[float, ...]
    translations: tuple[RegressionTranslationPredictions, ...]

    def __post_init__(self) -> None:
        if not self.opaque_context_id.strip():
            raise ValueError("opaque context identity is required")
        if not all(-1 <= value <= 1 for value in (self.research_control_stat, self.research_structure_stat)):
            raise ValueError("research correlation statistic must lie in [-1,1]")
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
        return self.research_structure_stat - self.research_control_stat


def load_v043_regression_submission(path: Path) -> V043RegressionSubmission:
    return parse_v043_regression_submission(json.loads(path.read_text()))


def parse_v043_regression_submission(payload: dict[str, Any]) -> V043RegressionSubmission:
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
            RegressionContextArtifact(
                opaque_context_id=str(context["opaque_context_id"]),
                research_control_stat=float(context["research_control_stat"]),
                research_structure_stat=float(context["research_structure_stat"]),
                independent_implication_strength=float(context["independent_implication_strength"]),
                control_confirmation_predictions=tuple(
                    float(value) for value in context["control_confirmation_predictions"]
                ),
                control_transfer_predictions=tuple(float(value) for value in context["control_transfer_predictions"]),
                translations=tuple(
                    RegressionTranslationPredictions(
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
                # V037PackSubmission is typed for V037ContextArtifact, but its own
                # validation and every downstream consumer (validate_v037_submission,
                # finalize scripts) only duck-type on the shared attributes (translations,
                # opaque_context_id, control_*_predictions) -- see module docstring.
                contexts=cast("tuple[Any, ...]", contexts),
            )
        )
    return V043RegressionSubmission(
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


def v043_regression_submission_contract() -> dict[str, Any]:
    """Return the complete agent-visible contract for a regression suite.

    Structurally identical to :func:`v037_agent.v037_submission_contract`, with only the
    AUC/probability-specific field descriptions replaced by their regression equivalents.
    """

    return {
        "version": REGRESSION_SUBMISSION_VERSION,
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
            "independent_implication": "non-correlation implication",
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
            "research_control_stat": "research-only Spearman correlation in [-1,1]",
            "research_structure_stat": "research-only Spearman correlation in [-1,1]",
            "independent_implication_strength": "research-only value in [0,1]",
            "control_confirmation_predictions": "aligned target-scale prediction list in confirmation file order",
            "control_transfer_predictions": "aligned target-scale prediction list in transfer file order",
            "translations": "at least two translation objects",
        },
        "translation_fields": {
            "candidate_id": "same candidate id must be used across contexts",
            "translation_kind": "non-empty free text",
            "confirmation_predictions": "aligned target-scale prediction list in confirmation file order",
            "transfer_predictions": "aligned target-scale prediction list in transfer file order",
        },
        "lock_rule": "all runs and both hidden-region predictions are locked before controller evaluation",
    }
