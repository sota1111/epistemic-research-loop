from __future__ import annotations

import hashlib

from epistemic_loop.benchmark.v037_repro_suite import (
    V037AliasTruth,
    V037ContextTruth,
    V037SuiteTruth,
)
from epistemic_loop.benchmark.v038_repro_suite import V038_QUAL_SUITE_IDS, V038_RUN_IDS
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
)
from epistemic_loop.controller.v038_agent import (
    NullReplicateProvenance,
    V038LoadedSubmission,
    V038SubmissionExtras,
)
from epistemic_loop.evaluation.calibration_v037 import fit_development_isotonic_map
from epistemic_loop.evaluation.v038 import assess_v038, evaluate_v038_runs


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _proposal(mode: V037ResearchMode, suffix: str) -> V037Proposal:
    return V037Proposal(
        mode=mode,
        lineage_id=f"{suffix}-{mode.value}",
        description=f"{suffix} {mode.value}",
        descriptor=V037ResearchDescriptor(
            hypothesis_family=f"family-{suffix}-{mode.value}",
            representation_family="representation",
            validation_world="forward",
            observation_unit="repeated",
            data_slice="all",
            experiment_operator="intervention",
            model_family="linear",
            downstream_decision="routing",
            structural_claim=mode is V037ResearchMode.EPISTEMIC,
        ),
        expected_decision="select translation",
        utility_mean=0.5,
        utility_std=0.1,
        competing_hypotheses=("link", "artifact") if mode is V037ResearchMode.EPISTEMIC else (),
        discriminating_observable="full-refit null" if mode is V037ResearchMode.EPISTEMIC else None,
    )


def _cycle(suffix: str) -> V037CycleRecord:
    return V037CycleRecord(
        cycle=1,
        proposals=tuple(_proposal(mode, suffix) for mode in V037ResearchMode),
        selected_lineage_id=f"{suffix}-epistemic",
        selected_mode=V037ResearchMode.EPISTEMIC,
        decision_changed=True,
        performance_improved=True,
        uncertainty_reduced=True,
        falsification_evidence_added=True,
        converted_to_parent_or_final=True,
        lineage_followup=True,
        lineage_explicitly_closed=True,
    )


def _truth(suite_id: str, suite_index: int) -> V037SuiteTruth:
    contexts: list[V037ContextTruth] = []
    aliases: list[V037AliasTruth] = []
    for pack_id, present in (("pack-positive", True), ("pack-negative", False)):
        for context_index in range(3):
            context_id = f"context-{context_index}"
            contexts.append(
                V037ContextTruth(
                    canonical_pack_id=pack_id,
                    canonical_context_id=context_id,
                    family="persistent" if present else "matched-null",
                    structure_present=present,
                    predictive_utility=present,
                    matched_pair="pair",
                    ladder_level=1,
                    generator_seed=context_index,
                    research_targets=(0, 1, 0, 1),
                    confirmation_targets=(0, 1, 0, 1),
                    transfer_targets=(0, 1, 0, 1),
                    oracle_research_predictions=(0.1, 0.9, 0.2, 0.8),
                    control_research_predictions=(0.4, 0.6, 0.4, 0.6),
                    oracle_confirmation_predictions=(0.1, 0.9, 0.2, 0.8),
                    control_confirmation_predictions=(0.4, 0.6, 0.4, 0.6),
                    oracle_transfer_predictions=(0.1, 0.9, 0.2, 0.8),
                    control_transfer_predictions=(0.4, 0.6, 0.4, 0.6),
                    independent_identifiability=0.2 if present else 0.0,
                )
            )
            for run_id in V038_RUN_IDS:
                agent_id, seed_text = run_id.rsplit("-s", 1)
                aliases.append(
                    V037AliasTruth(
                        run_id=run_id,
                        agent_id=agent_id,
                        sampling_seed=int(seed_text),
                        opaque_pack_id=f"{run_id}-{pack_id}",
                        opaque_context_id=f"{run_id}-{pack_id}-{context_id}",
                        canonical_pack_id=pack_id,
                        canonical_context_id=context_id,
                        canonical_to_visible_columns={"feature": "x"},
                        confirmation_targets_in_view_order=(0, 1, 0, 1),
                        transfer_targets_in_view_order=(0, 1, 0, 1),
                    )
                )
    return V037SuiteTruth(
        suite_id=suite_id,
        suite_index=suite_index,
        prompt_hashes={"p1": "hash"},
        policy_contract_hash="policy",
        generated_before_agent_runs=True,
        contexts_per_pack=3,
        context_truth=tuple(contexts),
        aliases=tuple(aliases),
    )


def _pack(run_id: str, present: bool) -> V037PackSubmission:
    pack_id = "pack-positive" if present else "pack-negative"
    control = (0.5, 0.5, 0.5, 0.5)
    strong = (0.1, 0.9, 0.2, 0.8)
    contexts = tuple(
        V037ContextArtifact(
            opaque_context_id=f"{run_id}-{pack_id}-context-{index}",
            research_control_auc=0.5,
            research_structure_auc=0.9 if present else 0.5,
            independent_implication_strength=0.2 if present else 0.0,
            control_confirmation_predictions=control,
            control_transfer_predictions=control,
            translations=(
                TranslationPredictions("translation-a", "history", strong if present else control, strong),
                TranslationPredictions("translation-b", "routing", strong if present else control, strong),
            ),
        )
        for index in range(3)
    )
    return V037PackSubmission(
        opaque_pack_id=f"{run_id}-{pack_id}",
        cycles=(_cycle(pack_id),),
        resolution=(V037Resolution.VALIDATED_ACTIONABLE_TRANSFERRED if present else V037Resolution.FALSIFIED),
        confidence=V037Confidence(0.9 if present else 0.1, 0.9, 0.8 if present else 0.1, 0.2),
        failure_trace=V037FailureTrace(True, True, True, present, present, True, True),
        claim="repeated relation" if present else "surface artifact",
        alternatives=("link", "frequency"),
        predicted_true="intervention changes prediction",
        predicted_false="matched null is equivalent",
        confounders=("frequency", "time"),
        falsification_conditions=("gain does not exceed null",),
        independent_implication="held-out coherence",
        affected_decisions=("aggregation", "routing"),
        causal_safety_passed=True,
        leave_one_context_out_stable=True,
        null_summary=FullRefitNullSummary(
            replicate_gains=(0.0,) * 5,
            all_replicates_refit_features_and_model=True,
            preserved_confounders=("frequency", "time"),
            destroyed_relation="linkage",
            stopping_reason=NullStoppingReason.EARLY_SUPPORT if present else NullStoppingReason.FUTILITY,
        ),
        selected_translation_id="translation-a",
        shadow_candidate_ids=("translation-b",),
        contexts=contexts,
    )


def _loaded(suite_id: str, run_id: str) -> V038LoadedSubmission:
    agent_id, seed_text = run_id.rsplit("-s", 1)
    packs = (_pack(run_id, True), _pack(run_id, False))
    core = V037AgentSubmission(
        version="0.3.7",
        suite_id=suite_id,
        run_id=run_id,
        agent_id=agent_id,
        sampling_seed=int(seed_text),
        prompt_arm="p1",
        lineage_policy=LineagePolicy.DETERMINISTIC_BEST,
        prompt_hash="hash",
        policy_contract_hash="policy",
        human_assisted=False,
        cross_run_information_used=False,
        artifact_complete=True,
        oof_honesty_passed=True,
        hidden_isolation_passed=True,
        packs=packs,
    )
    provenance = {
        pack.opaque_pack_id: tuple(
            NullReplicateProvenance(
                replicate_index=index + 1,
                permutation_hash=_digest(f"{run_id}-{pack.opaque_pack_id}-permutation-{index}"),
                preserved_statistics={"frequency_mean": 0.5},
                feature_manifest_hash=_digest(f"{run_id}-{pack.opaque_pack_id}-features-{index}"),
                fold_plan_hash=_digest(f"{run_id}-{pack.opaque_pack_id}-folds-{index}"),
                model_fit_manifest_hash=_digest(f"{run_id}-{pack.opaque_pack_id}-model-{index}"),
                oof_prediction_hash=_digest(f"{run_id}-{pack.opaque_pack_id}-oof-{index}"),
                gain=gain,
            )
            for index, gain in enumerate(pack.null_summary.replicate_gains)
        )
        for pack in packs
    }
    return V038LoadedSubmission(core=core, extras=V038SubmissionExtras("0.3.8", provenance))


def test_v038_evaluation_reuses_strict_gates_and_adds_audits() -> None:
    truths = tuple(_truth(suite_id, index) for index, suite_id in enumerate(V038_QUAL_SUITE_IDS, start=1))
    loaded = tuple(_loaded(suite_id, run_id) for suite_id in V038_QUAL_SUITE_IDS for run_id in V038_RUN_IDS)
    calibration_map = fit_development_isotonic_map(
        tuple([0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9]),
        tuple([False, False, False, True, False, True, True, True]),
    )

    report = evaluate_v038_runs(loaded, truths, calibration_map)

    assert report.base.median_agent_tsdr == 1.0
    assert report.base.median_agent_tsrr == 1.0
    assert report.base.worst_agent_fspr == 0.0
    audit = report.provenance_audit
    assert audit.pack_count == 48
    assert audit.executed_null_packs == 48
    assert audit.packs_with_complete_provenance == 48
    assert audit.provenance_status == "MACHINE_AUDITED_DECLARED"
    assert report.tsdr_cluster_interval.blocks == 8
    assert report.tsdr_cluster_interval.lower <= report.tsdr_cluster_interval.estimate == 1.0
    assert report.fspr_cluster_interval.estimate == 0.0
    assert all(item.calibrated is not None for item in report.agent_structure_calibration)
    assert report.mean_pairwise_operator_jaccard == 1.0
    assert set(report.per_agent_distinct_operators) == {"agent-01", "agent-02", "agent-03"}
    assert report.adjudicated_failure_stage_counts == {}

    acceptance = assess_v038(report)
    assert acceptance.base.median_agent_tsdr
    assert acceptance.calibrated_median_structure_brier is not None


def test_v038_incomplete_provenance_is_reported() -> None:
    truths = tuple(_truth(suite_id, index) for index, suite_id in enumerate(V038_QUAL_SUITE_IDS, start=1))
    loaded = list(_loaded(suite_id, run_id) for suite_id in V038_QUAL_SUITE_IDS for run_id in V038_RUN_IDS)
    stripped = loaded[0]
    loaded[0] = V038LoadedSubmission(core=stripped.core, extras=V038SubmissionExtras("0.3.8", {}))

    report = evaluate_v038_runs(tuple(loaded), truths, None)

    assert report.provenance_audit.packs_with_complete_provenance == 46
    assert report.provenance_audit.provenance_status == "INCOMPLETE"
    assert all(item.calibrated is None for item in report.agent_structure_calibration)
