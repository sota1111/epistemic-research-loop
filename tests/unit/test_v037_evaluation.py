from __future__ import annotations

from dataclasses import replace

from epistemic_loop.benchmark.v037_repro_suite import (
    V037_AGENT_IDS,
    V037_RUN_IDS,
    V037_SAMPLING_SEEDS,
    V037_SUITE_IDS,
    V037AliasTruth,
    V037ContextTruth,
    V037SuiteTruth,
)
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
from epistemic_loop.evaluation.v037 import evaluate_v037_runs


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
            for run_id in V037_RUN_IDS:
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
        prompt_hashes={"p0": "hash", "p1": "hash"},
        policy_contract_hash="policy",
        generated_before_agent_runs=True,
        contexts_per_pack=3,
        context_truth=tuple(contexts),
        aliases=tuple(aliases),
    )


def _pack(run_id: str, present: bool, negative_transfer: bool) -> V037PackSubmission:
    pack_id = "pack-positive" if present else "pack-negative"
    control = (0.5, 0.5, 0.5, 0.5)
    confirmation = (0.1, 0.9, 0.2, 0.8) if present else control
    transfer = (0.9, 0.1, 0.8, 0.2) if negative_transfer and present else confirmation
    contexts = tuple(
        V037ContextArtifact(
            opaque_context_id=f"{run_id}-{pack_id}-context-{index}",
            research_control_auc=0.5,
            research_structure_auc=0.9 if present else 0.5,
            independent_implication_strength=0.2 if present else 0.0,
            control_confirmation_predictions=control,
            control_transfer_predictions=control,
            translations=(
                TranslationPredictions("translation-a", "history", confirmation, transfer),
                TranslationPredictions("translation-b", "routing", confirmation, transfer),
            ),
        )
        for index in range(3)
    )
    return V037PackSubmission(
        opaque_pack_id=f"{run_id}-{pack_id}",
        cycles=(_cycle(pack_id),),
        resolution=(V037Resolution.VALIDATED_ACTIONABLE_NOT_TRANSFERRED if present else V037Resolution.FALSIFIED),
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


def test_v037_discovery_does_not_use_transfer_labels() -> None:
    truths = tuple(_truth(suite_id, index) for index, suite_id in enumerate(V037_SUITE_IDS, start=1))
    submissions: list[V037AgentSubmission] = []
    for suite_id in V037_SUITE_IDS:
        for run_id in V037_RUN_IDS:
            agent_id, seed_text = run_id.rsplit("-s", 1)
            submissions.append(
                V037AgentSubmission(
                    version="0.3.7",
                    suite_id=suite_id,
                    run_id=run_id,
                    agent_id=agent_id,
                    sampling_seed=int(seed_text),
                    prompt_arm="p0",
                    lineage_policy=LineagePolicy.DETERMINISTIC_BEST,
                    prompt_hash="hash",
                    policy_contract_hash="policy",
                    human_assisted=False,
                    cross_run_information_used=False,
                    artifact_complete=True,
                    oof_honesty_passed=True,
                    hidden_isolation_passed=True,
                    packs=(_pack(run_id, True, True), _pack(run_id, False, False)),
                )
            )

    report = evaluate_v037_runs(tuple(submissions), truths)

    assert report.median_agent_tsdr == 1.0
    assert report.median_agent_tsrr == 1.0
    assert report.worst_agent_fspr == 0.0
    assert report.median_ustr == 0.0
    assert report.median_structure_gain is not None and report.median_structure_gain < 0
    assert report.persistent_agents_discovering == len(V037_AGENT_IDS)
    assert len(report.agent_aggregates) == len(V037_AGENT_IDS)
    assert len(report.agent_seed_aggregates) == len(V037_AGENT_IDS) * len(V037_SAMPLING_SEEDS)
    assert all(item.runs == len(V037_SUITE_IDS) * len(V037_SAMPLING_SEEDS) for item in report.agent_aggregates)
    assert all(item.runs == len(V037_SUITE_IDS) for item in report.agent_seed_aggregates)
    assert all(item.tsdr_interval.trials == 8 for item in report.agent_aggregates)
    assert {item.sampling_seed for item in report.runs} == set(V037_SAMPLING_SEEDS)


def test_v037_confirmation_does_not_oracle_select_a_translation() -> None:
    truths = tuple(_truth(suite_id, index) for index, suite_id in enumerate(V037_SUITE_IDS, start=1))
    submissions: list[V037AgentSubmission] = []
    changed_pair = (V037_SUITE_IDS[0], V037_RUN_IDS[0])
    for suite_id in V037_SUITE_IDS:
        for run_id in V037_RUN_IDS:
            agent_id, seed_text = run_id.rsplit("-s", 1)
            positive = _pack(run_id, True, False)
            if (suite_id, run_id) == changed_pair:
                contexts = tuple(
                    replace(
                        context,
                        translations=(
                            replace(
                                context.translations[0],
                                confirmation_predictions=(0.9, 0.1, 0.8, 0.2),
                            ),
                            context.translations[1],
                        ),
                    )
                    for context in positive.contexts
                )
                positive = replace(positive, contexts=contexts)
            submissions.append(
                V037AgentSubmission(
                    version="0.3.7",
                    suite_id=suite_id,
                    run_id=run_id,
                    agent_id=agent_id,
                    sampling_seed=int(seed_text),
                    prompt_arm="p0",
                    lineage_policy=LineagePolicy.DETERMINISTIC_BEST,
                    prompt_hash="hash",
                    policy_contract_hash="policy",
                    human_assisted=False,
                    cross_run_information_used=False,
                    artifact_complete=True,
                    oof_honesty_passed=True,
                    hidden_isolation_passed=True,
                    packs=(positive, _pack(run_id, False, False)),
                )
            )

    report = evaluate_v037_runs(tuple(submissions), truths)
    changed = next(
        item for item in report.packs if (item.suite_id, item.run_id) == changed_pair and item.structure_present
    )
    assert not changed.behaviorally_discovered
    assert changed.failure_stage == "evidence"
