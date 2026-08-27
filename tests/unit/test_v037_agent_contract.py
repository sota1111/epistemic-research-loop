from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

from epistemic_loop.controller.v037_agent import (
    FullRefitNullSummary,
    LineagePolicy,
    NullStoppingReason,
    TranslationPredictions,
    V037AgentSubmission,
    V037Confidence,
    V037ContextArtifact,
    V037CycleRecord,
    V037FailureTrace,
    V037PackSubmission,
    V037Proposal,
    V037ResearchDescriptor,
    V037ResearchMode,
    V037Resolution,
    load_v037_submission,
    validate_v037_submission,
)


def _proposal(mode: V037ResearchMode) -> V037Proposal:
    return V037Proposal(
        mode=mode,
        lineage_id=f"lineage-{mode.value}",
        description=f"test {mode.value}",
        descriptor=V037ResearchDescriptor(
            hypothesis_family=f"family-{mode.value}",
            representation_family="representation",
            validation_world="forward",
            observation_unit="unknown",
            data_slice="all",
            experiment_operator="comparison",
            model_family="linear",
            downstream_decision="candidate",
            structural_claim=mode is V037ResearchMode.EPISTEMIC,
        ),
        expected_decision="retain or reject",
        utility_mean=0.5,
        utility_std=0.1,
        competing_hypotheses=("linked", "artifact") if mode is V037ResearchMode.EPISTEMIC else (),
        discriminating_observable="refit-null gain" if mode is V037ResearchMode.EPISTEMIC else None,
    )


def _context(index: int) -> V037ContextArtifact:
    translations = tuple(
        TranslationPredictions(
            candidate_id=candidate,
            translation_kind=kind,
            confirmation_predictions=(0.2, 0.8),
            transfer_predictions=(0.3, 0.7),
        )
        for candidate, kind in (("translation-a", "history"), ("translation-b", "routing"))
    )
    return V037ContextArtifact(
        opaque_context_id=f"context-{index}",
        research_control_auc=0.6,
        research_structure_auc=0.7,
        independent_implication_strength=0.2,
        control_confirmation_predictions=(0.4, 0.6),
        control_transfer_predictions=(0.4, 0.6),
        translations=translations,
    )


def test_v037_contract_accepts_decomposed_confidence_and_full_refit_null(tmp_path: Path) -> None:
    cycle = V037CycleRecord(
        cycle=1,
        proposals=tuple(_proposal(mode) for mode in V037ResearchMode),
        selected_lineage_id="lineage-epistemic",
        selected_mode=V037ResearchMode.EPISTEMIC,
        decision_changed=True,
        performance_improved=False,
        uncertainty_reduced=True,
        falsification_evidence_added=True,
        converted_to_parent_or_final=True,
        lineage_followup=True,
        lineage_explicitly_closed=False,
    )
    pack = V037PackSubmission(
        opaque_pack_id="opaque-pack",
        cycles=(cycle,),
        resolution=V037Resolution.VALIDATED_ACTIONABLE_TRANSFERRED,
        confidence=V037Confidence(0.8, 0.75, 0.7, 0.6),
        failure_trace=V037FailureTrace(True, True, True, True, True, True, True),
        claim="a repeated relation changes multiple decisions",
        alternatives=("persistent relation", "frequency artifact"),
        predicted_true="link intervention changes outcomes",
        predicted_false="matched null is equivalent",
        confounders=("frequency", "time"),
        falsification_conditions=("real gain does not exceed refit null",),
        independent_implication="held-out relation remains coherent",
        affected_decisions=("representation", "routing"),
        causal_safety_passed=True,
        leave_one_context_out_stable=True,
        null_summary=FullRefitNullSummary(
            replicate_gains=(0.0, 0.01, -0.01, 0.005, 0.0),
            all_replicates_refit_features_and_model=True,
            preserved_confounders=("frequency", "time"),
            destroyed_relation="cross-row linkage",
            stopping_reason=NullStoppingReason.EARLY_SUPPORT,
        ),
        selected_translation_id="translation-a",
        shadow_candidate_ids=("translation-b",),
        contexts=tuple(_context(index) for index in range(3)),
    )
    submission = V037AgentSubmission(
        version="0.3.7",
        suite_id="v037-repro-b01",
        run_id="agent-01-s17",
        agent_id="agent-01",
        sampling_seed=17,
        prompt_arm="p0",
        lineage_policy=LineagePolicy.DETERMINISTIC_BEST,
        prompt_hash="hash",
        policy_contract_hash="policy",
        human_assisted=False,
        cross_run_information_used=False,
        artifact_complete=True,
        oof_honesty_passed=True,
        hidden_isolation_passed=True,
        packs=(pack,),
    )
    assert submission.packs[0].failure_trace.failure_stage == "none"
    path = tmp_path / "submission.json"
    path.write_text(json.dumps(asdict(submission)))
    loaded = load_v037_submission(path)
    packet = {
        "suite_id": submission.suite_id,
        "run_id": submission.run_id,
        "agent_id": submission.agent_id,
        "sampling_seed": submission.sampling_seed,
        "prompt_arm": submission.prompt_arm,
        "prompt_hash": submission.prompt_hash,
        "policy_contract_hash": submission.policy_contract_hash,
        "lineage_policy": submission.lineage_policy.value,
        "packs": [
            {
                "opaque_pack_id": "opaque-pack",
                "contexts": [
                    {
                        "opaque_context_id": f"context-{index}",
                        "confirmation_rows": 2,
                        "transfer_rows": 2,
                    }
                    for index in range(3)
                ],
            }
        ],
    }
    assert validate_v037_submission(loaded, packet).valid

    invalid = replace(
        loaded,
        suite_id="wrong-suite",
        human_assisted=True,
        cross_run_information_used=True,
        artifact_complete=False,
        oof_honesty_passed=False,
        hidden_isolation_passed=False,
    )
    errors = validate_v037_submission(invalid, packet).errors
    assert "suite_id mismatch" in errors
    assert "human-assisted primary run" in errors
    assert "cross-run information used" in errors
    assert "artifact contract incomplete" in errors
    assert "OOF honesty failed" in errors
    assert "hidden isolation failed" in errors


def test_v037_terminal_resolution_rejects_fixed_prediction_null() -> None:
    try:
        FullRefitNullSummary(
            replicate_gains=(0.0,) * 5,
            all_replicates_refit_features_and_model=False,
            preserved_confounders=("frequency",),
            destroyed_relation="linkage",
            stopping_reason=NullStoppingReason.FUTILITY,
        )
    except ValueError:
        raise AssertionError("null summary alone may record an invalid design for audit") from None

    cycle = V037CycleRecord(
        cycle=1,
        proposals=tuple(_proposal(mode) for mode in V037ResearchMode),
        selected_lineage_id="lineage-epistemic",
        selected_mode=V037ResearchMode.EPISTEMIC,
        decision_changed=False,
        performance_improved=False,
        uncertainty_reduced=True,
        falsification_evidence_added=True,
        converted_to_parent_or_final=False,
        lineage_followup=False,
        lineage_explicitly_closed=True,
    )
    try:
        V037PackSubmission(
            opaque_pack_id="pack",
            cycles=(cycle,),
            resolution=V037Resolution.FALSIFIED,
            confidence=V037Confidence(0.1, 0.8, 0.1, 0.1),
            failure_trace=V037FailureTrace(True, True, True, False, False, True, True),
            claim="linkage artifact",
            alternatives=("link", "frequency"),
            predicted_true="gain",
            predicted_false="no gain",
            confounders=("frequency",),
            falsification_conditions=("no gain",),
            independent_implication="none",
            affected_decisions=("representation",),
            causal_safety_passed=True,
            leave_one_context_out_stable=True,
            null_summary=FullRefitNullSummary(
                replicate_gains=(0.0,) * 5,
                all_replicates_refit_features_and_model=False,
                preserved_confounders=("frequency",),
                destroyed_relation="linkage",
                stopping_reason=NullStoppingReason.FUTILITY,
            ),
            selected_translation_id="translation-a",
            shadow_candidate_ids=("translation-b",),
            contexts=tuple(_context(index) for index in range(3)),
        )
    except ValueError as error:
        assert "full-refit null" in str(error)
    else:
        raise AssertionError("fixed-prediction null was accepted for a terminal decision")
