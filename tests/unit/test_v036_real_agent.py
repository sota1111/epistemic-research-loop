from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from pathlib import Path

from cryptography.fernet import Fernet

from epistemic_loop.benchmark.v036_blind_suite import (
    DEFAULT_AGENTS,
    AgentAliasTruth,
    ContextTruth,
    SuiteTruth,
    build_blind_structure_suite,
    decrypt_suite_truth,
)
from epistemic_loop.controller.v036_real_agent import (
    CommunicationMode,
    ContextPredictionArtifact,
    MigrationPacket,
    PackResearchSubmission,
    RealAgentSubmission,
    StructureResolution,
    V036CycleRecord,
    V036Proposal,
    V036ResearchDescriptor,
    V036ResearchMode,
)
from epistemic_loop.evaluation.v036 import V036Acceptance, V036Reliability, V036Status, evaluate_real_agent_population


def _proposal(mode: V036ResearchMode, family: str) -> V036Proposal:
    return V036Proposal(
        mode=mode,
        description=f"{mode.value} {family}",
        descriptor=V036ResearchDescriptor(
            hypothesis_family=family,
            representation_family=f"representation-{family}",
            validation_world="context-forward",
            observation_unit=f"unit-{family}",
            data_slice=f"slice-{family}",
            experiment_operator=f"operator-{family}",
            model_family="capacity-matched-linear",
            downstream_decision=f"decision-{family}",
            structural_claim=mode is V036ResearchMode.EPISTEMIC,
        ),
        expected_decision=f"decide {family}",
        competing_hypotheses=("structure", "artifact") if mode is V036ResearchMode.EPISTEMIC else (),
        discriminating_observable="matched-null gain" if mode is V036ResearchMode.EPISTEMIC else None,
    )


def _cycle(index: int, family: str, selected: V036ResearchMode) -> V036CycleRecord:
    return V036CycleRecord(
        cycle=index,
        proposals=tuple(_proposal(mode, f"{family}-{mode.value}") for mode in V036ResearchMode),
        selected_mode=selected,
        selected_description=f"selected {selected.value}",
        decision_changed=True,
        performance_improved=selected is V036ResearchMode.EXPLOIT,
        uncertainty_reduced=selected is V036ResearchMode.EPISTEMIC,
        falsification_evidence_added=selected is V036ResearchMode.EPISTEMIC,
        converted_to_parent_or_final=selected is not V036ResearchMode.EXPLOIT,
    )


def _submissions(truth: SuiteTruth) -> tuple[RealAgentSubmission, ...]:
    truth_context = {(item.canonical_pack_id, item.canonical_context_id): item for item in truth.context_truth}
    grouped: dict[tuple[str, str], list[AgentAliasTruth]] = defaultdict(list)
    for alias in truth.aliases:
        grouped[alias.agent_id, alias.opaque_pack_id].append(alias)
    output: list[RealAgentSubmission] = []
    for agent_index, agent in enumerate(DEFAULT_AGENTS):
        packs: list[PackResearchSubmission] = []
        for pack_index, ((_, opaque_pack), aliases) in enumerate(
            sorted((key, value) for key, value in grouped.items() if key[0] == agent),
            start=1,
        ):
            context_truth: list[ContextTruth] = [
                truth_context[alias.canonical_pack_id, alias.canonical_context_id] for alias in aliases
            ]
            present = context_truth[0].structure_present
            contexts = tuple(
                ContextPredictionArtifact(
                    opaque_context_id=alias.opaque_context_id,
                    research_control_auc=0.60,
                    research_structure_auc=0.80 if present else 0.60,
                    null_gain_95th_percentile=0.01,
                    independent_implication_strength=0.40 if present else 0.01,
                    control_predictions=item.control_sealed_predictions,
                    structure_predictions=(
                        item.oracle_sealed_predictions if present else item.control_sealed_predictions
                    ),
                )
                for alias, item in zip(aliases, context_truth, strict=True)
            )
            selected = tuple(V036ResearchMode)[(pack_index + agent_index) % 3]
            packs.append(
                PackResearchSubmission(
                    opaque_pack_id=opaque_pack,
                    cycles=(_cycle(1, f"family-{pack_index}", selected),),
                    resolution=(StructureResolution.VALIDATED_ACTIONABLE if present else StructureResolution.FALSIFIED),
                    confidence=0.90 if present else 0.10,
                    claim="a repeated relation changes the prediction decision",
                    alternatives=("persistent relation", "marginal artifact"),
                    predicted_true="matched intervention gain is stable",
                    predicted_false="matched intervention gain disappears",
                    confounders=("frequency", "time"),
                    falsification_conditions=("gain does not exceed matched null",),
                    independent_implication="held-out relation changes",
                    affected_decisions=("representation", "routing"),
                    matched_null_executed=True,
                    causal_safety_passed=True,
                    leave_one_context_out_stable=True,
                    selected_candidate_id=f"candidate-{pack_index}",
                    shadow_candidate_ids=(f"shadow-{pack_index}",),
                    contexts=contexts,
                )
            )
        output.append(
            RealAgentSubmission(
                version="0.3.6",
                suite_id=truth.suite_id,
                agent_id=agent,
                prompt_hash=truth.prompt_hash,
                human_assisted=False,
                cross_agent_information_used=False,
                artifact_complete=True,
                oof_honesty_passed=True,
                sealed_isolation_passed=True,
                packs=tuple(packs),
            )
        )
    return tuple(output)


def test_real_agent_population_passes_when_behavior_matches_blind_truth(tmp_path: Path) -> None:
    key = Fernet.generate_key()
    result = build_blind_structure_suite(
        suite_id="real-agent-eval",
        suite_kind="qualification",
        output_root=tmp_path / "public",
        truth_root=tmp_path / "private",
        key=key,
        prompt_hash="prompt",
        rows_per_context=600,
    )
    truth = decrypt_suite_truth(Path(result.encrypted_truth_path), key)
    report = evaluate_real_agent_population(_submissions(truth), truth)
    reliability = V036Reliability(0, 0, 0, 0, 1.0, 1.0, 1.0, 0)
    acceptance = V036Acceptance.assess(report, reliability)

    assert report.population_union_tsdr == 1.0
    assert report.population_union_tsrr == 1.0
    assert report.population_union_fspr == 0.0
    assert report.useful_structure_transfer_rate == 1.0
    assert report.exploration_to_exploitation_conversion > 0
    assert acceptance.overall is V036Status.PASS


def test_communication_packets_enforce_information_boundaries() -> None:
    MigrationPacket(CommunicationMode.EVIDENCE, "a", "b", evidence=("replicated fact",))
    MigrationPacket(
        CommunicationMode.DEBT,
        "a",
        "b",
        evidence=("replicated fact",),
        unresolved_questions=("does it survive a null?",),
    )
    try:
        MigrationPacket(CommunicationMode.EVIDENCE, "a", "b", scores=(0.9,))
    except ValueError as error:
        assert "evidence mode" in str(error)
    else:
        raise AssertionError("evidence-only migration leaked a score")


def test_structure_discovery_does_not_make_transfer_tautological(tmp_path: Path) -> None:
    key = Fernet.generate_key()
    result = build_blind_structure_suite(
        suite_id="real-agent-transfer-separation",
        suite_kind="qualification",
        output_root=tmp_path / "public",
        truth_root=tmp_path / "private",
        key=key,
        prompt_hash="prompt",
        rows_per_context=600,
    )
    truth = decrypt_suite_truth(Path(result.encrypted_truth_path), key)
    submissions = list(_submissions(truth))
    first = submissions[0]
    positive_index = next(
        index
        for index, pack in enumerate(first.packs)
        if next(
            context
            for context in truth.context_truth
            if context.canonical_pack_id
            == next(
                alias.canonical_pack_id
                for alias in truth.aliases
                if alias.agent_id == first.agent_id and alias.opaque_pack_id == pack.opaque_pack_id
            )
        ).structure_present
    )
    positive = first.packs[positive_index]
    degraded_contexts = tuple(
        replace(
            context,
            structure_predictions=tuple(1 - value for value in context.control_predictions),
        )
        for context in positive.contexts
    )
    packs = list(first.packs)
    packs[positive_index] = replace(positive, contexts=degraded_contexts)
    submissions[0] = replace(first, packs=tuple(packs))

    report = evaluate_real_agent_population(tuple(submissions), truth)
    degraded = next(
        item
        for item in report.evaluated_packs
        if item.agent_id == first.agent_id
        and item.canonical_pack_id
        == next(
            alias.canonical_pack_id
            for alias in truth.aliases
            if alias.agent_id == first.agent_id and alias.opaque_pack_id == positive.opaque_pack_id
        )
    )
    assert degraded.behaviorally_validated
    assert degraded.median_sealed_gain < 0
    assert report.useful_structure_transfer_rate is not None
    assert report.useful_structure_transfer_rate < 1.0
