from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet

from epistemic_loop.benchmark.v037_repro_suite import CANONICAL_FEATURES
from epistemic_loop.benchmark.v040_grammar_suite import (
    V040_GEN1_CONFIGS,
    V040_GEN1_EXCLUDED_RUNS,
    V040_GEN1_SUITE_IDS,
    V040_RUN_IDS,
    accept_grammar_spec,
    build_v040_suite,
    generate_grammar_context,
    sample_grammar_spec,
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
from epistemic_loop.controller.v040_agent import (
    load_v040_submission,
    v040_submission_contract,
    validate_v040_submission,
)


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def test_grammar_spec_and_context_are_deterministic_and_schema_complete() -> None:
    spec_a = sample_grammar_spec(random.Random(7))
    spec_b = sample_grammar_spec(random.Random(7))
    assert spec_a == spec_b
    assert 2 <= len(spec_a.motifs) <= 3
    rows = generate_grammar_context(spec_a, structure_on=True, seed=11, count=600)
    again = generate_grammar_context(spec_a, structure_on=True, seed=11, count=600)
    assert rows == again
    assert set(rows[0]) >= set(CANONICAL_FEATURES) | {"row_id", "target", "_oracle", "_control"}
    null_rows = generate_grammar_context(spec_a, structure_on=False, seed=11, count=600)
    assert all(row["_oracle"] == row["_control"] for row in null_rows)


def test_grammar_acceptance_finds_identifiable_spec() -> None:
    spec = accept_grammar_spec(
        master_seed=20260910,
        suite_id=V040_GEN1_SUITE_IDS[0],
        pair="grammar-a",
        contexts_per_pack=3,
        rows_per_context=600,
    )
    assert spec.motifs


def test_preregistered_exclusions_match_the_deviation_record() -> None:
    preregistration = json.loads(Path("docs/v040_gen1_preregistration.json").read_text())
    deviations = preregistration["post_registration_deviations"]
    active_exclusions = {
        f"{item['run'].split('/')[0]}/{item['run'].split('/')[1]}"
        for item in deviations
        if "run" in item and item.get("status") != "SUPERSEDED by the entry below (root cause fixed, run reinstated)"
    }
    assert active_exclusions == {f"{suite}/{run}" for suite, run in V040_GEN1_EXCLUDED_RUNS}
    assert deviations[-1]["effective_run_count"] == preregistration["total_runs"] - len(V040_GEN1_EXCLUDED_RUNS)
    for suite, run in V040_GEN1_EXCLUDED_RUNS:
        assert suite in V040_GEN1_SUITE_IDS
        assert run in V040_RUN_IDS


def test_v040_suite_build_assigns_per_slot_prompts(tmp_path: Path) -> None:
    key = Fernet.generate_key()
    p1 = tmp_path / "p1.md"
    p2 = tmp_path / "p2.md"
    p1.write_text("prompt one\n")
    p2.write_text("prompt two\n")
    contract = {
        "null_policy": {"minimum": 5, "maximum": 30, "provenance_required": True},
        "confidence_fields": ["p_structure_exists"],
    }
    result = build_v040_suite(
        suite_id=V040_GEN1_SUITE_IDS[0],
        output_root=tmp_path / "public",
        truth_root=tmp_path / "truth",
        key=key,
        prompt_paths={"p1": p1, "p2": p2},
        policy_contract=contract,
        rows_per_context=600,
    )
    assert result.preflight_passed
    assert len(result.preflight) == 14
    for run_id in V040_RUN_IDS:
        packet = json.loads((tmp_path / "public" / "agent_views" / run_id / "agent_packet.json").read_text())
        assert packet["version"] == "0.4.0"
        assert packet["prompt_arm"] == V040_GEN1_CONFIGS[run_id]["prompt_arm"]
        assert packet["lineage_policy"] == "posterior_commit"
        assert packet["implication_provenance_required"] is True
        assert len(packet["packs"]) == 14
        prompt = (tmp_path / "public" / "agent_views" / run_id / "agent_prompt.md").read_text()
        expected = "prompt one\n" if packet["prompt_arm"] == "p1" else "prompt two\n"
        assert prompt == expected
    with pytest.raises(FileExistsError, match="immutable"):
        build_v040_suite(
            suite_id=V040_GEN1_SUITE_IDS[0],
            output_root=tmp_path / "public",
            truth_root=tmp_path / "truth",
            key=key,
            prompt_paths={"p1": p1, "p2": p2},
            policy_contract=contract,
            rows_per_context=600,
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


def _pack(resolution: V037Resolution, *, implication: float) -> V037PackSubmission:
    cycle = V037CycleRecord(
        cycle=1,
        proposals=tuple(_proposal(mode) for mode in V037ResearchMode),
        selected_lineage_id="lineage-epistemic",
        selected_mode=V037ResearchMode.EPISTEMIC,
        decision_changed=True,
        performance_improved=False,
        uncertainty_reduced=True,
        falsification_evidence_added=resolution is V037Resolution.FALSIFIED,
        converted_to_parent_or_final=True,
        lineage_followup=True,
        lineage_explicitly_closed=True,
    )
    contexts = tuple(
        V037ContextArtifact(
            opaque_context_id=f"context-{index}",
            research_control_auc=0.6,
            research_structure_auc=0.6,
            independent_implication_strength=implication,
            control_confirmation_predictions=(0.4, 0.6),
            control_transfer_predictions=(0.4, 0.6),
            translations=(
                TranslationPredictions("translation-a", "history", (0.2, 0.8), (0.3, 0.7)),
                TranslationPredictions("translation-b", "routing", (0.2, 0.8), (0.3, 0.7)),
            ),
        )
        for index in range(3)
    )
    return V037PackSubmission(
        opaque_pack_id="opaque-pack",
        cycles=(cycle,),
        resolution=resolution,
        confidence=V037Confidence(0.5, 0.5, 0.5, 0.5),
        failure_trace=V037FailureTrace(True, True, True, True, True, True, True),
        claim="claim",
        alternatives=("one", "two"),
        predicted_true="gain",
        predicted_false="no gain",
        confounders=("frequency",),
        falsification_conditions=("no gain",),
        independent_implication="held-out coherence",
        affected_decisions=("routing",),
        causal_safety_passed=True,
        leave_one_context_out_stable=True,
        null_summary=FullRefitNullSummary(
            replicate_gains=(0.0, 0.005, -0.004, 0.002, 0.01),
            all_replicates_refit_features_and_model=True,
            preserved_confounders=("frequency",),
            destroyed_relation="linkage",
            stopping_reason=NullStoppingReason.FUTILITY,
        ),
        selected_translation_id="translation-a",
        shadow_candidate_ids=("translation-b",),
        contexts=contexts,
    )


def _payload(pack: V037PackSubmission, positions: tuple[float, ...] | None) -> dict[str, Any]:
    submission = V037AgentSubmission(
        version="0.3.7",
        suite_id="v040-genA-g01",
        run_id="agent-01-s17",
        agent_id="agent-01",
        sampling_seed=17,
        prompt_arm="p1",
        lineage_policy=LineagePolicy.POSTERIOR_COMMIT,
        prompt_hash="hash",
        policy_contract_hash="policy",
        human_assisted=False,
        cross_run_information_used=False,
        artifact_complete=True,
        oof_honesty_passed=True,
        hidden_isolation_passed=True,
        packs=(pack,),
    )
    payload = asdict(submission)
    payload["version"] = "0.4.0"
    raw_pack = payload["packs"][0]
    raw_pack["null_summary"]["replicates"] = [
        {
            "replicate_index": index + 1,
            "permutation_hash": _digest(f"perm-{index}"),
            "preserved_statistics": {"frequency_mean": 0.5},
            "feature_manifest_hash": _digest(f"feat-{index}"),
            "fold_plan_hash": _digest(f"fold-{index}"),
            "model_fit_manifest_hash": _digest(f"model-{index}"),
            "oof_prediction_hash": _digest(f"oof-{index}"),
            "gain": gain,
        }
        for index, gain in enumerate(pack.null_summary.replicate_gains)
    ]
    if positions is not None:
        for index, context in enumerate(raw_pack["contexts"]):
            context["implication_provenance"] = {
                "statistic": "held-out coherence position",
                "held_out": True,
                "null_reference_position": positions[index],
                "computation_hash": _digest(f"implication-{index}"),
            }
    return payload


def _packet() -> dict[str, Any]:
    return {
        "version": "0.4.0",
        "suite_id": "v040-genA-g01",
        "run_id": "agent-01-s17",
        "agent_id": "agent-01",
        "sampling_seed": 17,
        "prompt_arm": "p1",
        "prompt_hash": "hash",
        "policy_contract_hash": "policy",
        "lineage_policy": "posterior_commit",
        "packs": [
            {
                "opaque_pack_id": "opaque-pack",
                "contexts": [
                    {"opaque_context_id": f"context-{index}", "confirmation_rows": 2, "transfer_rows": 2}
                    for index in range(3)
                ],
            }
        ],
    }


def _load(tmp_path: Path, payload: dict[str, Any]):
    path = tmp_path / "agent_submission.json"
    path.write_text(json.dumps(payload))
    return load_v040_submission(path)


def test_v040_terminal_resolution_requires_implication_provenance(tmp_path: Path) -> None:
    missing = _load(tmp_path, _payload(_pack(V037Resolution.FALSIFIED, implication=0.0), None))
    errors = validate_v040_submission(missing, _packet()).errors
    assert any("requires implication provenance" in item for item in errors)

    consistent = _load(
        tmp_path,
        _payload(_pack(V037Resolution.FALSIFIED, implication=0.0), (0.4, 0.6, 0.2)),
    )
    validation = validate_v040_submission(consistent, _packet())
    assert validation.valid, validation.errors

    inconsistent = _load(
        tmp_path,
        _payload(_pack(V037Resolution.FALSIFIED, implication=0.0), (0.99, 0.97, 0.2)),
    )
    errors = validate_v040_submission(inconsistent, _packet()).errors
    assert any("null-referenced implication positions" in item for item in errors)


def test_v040_promotion_requires_null_referenced_support(tmp_path: Path) -> None:
    weak = _load(
        tmp_path,
        _payload(_pack(V037Resolution.VALIDATED_NON_ACTIONABLE, implication=0.4), (0.5, 0.4, 0.3)),
    )
    errors = validate_v040_submission(weak, _packet()).errors
    assert any("at least two contexts" in item for item in errors)

    strong = _load(
        tmp_path,
        _payload(_pack(V037Resolution.VALIDATED_NON_ACTIONABLE, implication=0.4), (0.99, 0.98, 0.3)),
    )
    assert validate_v040_submission(strong, _packet()).valid

    inconclusive = _load(tmp_path, _payload(_pack(V037Resolution.INCONCLUSIVE, implication=0.4), None))
    assert validate_v040_submission(inconclusive, _packet()).valid


def test_v040_contract_documents_provenance_rule() -> None:
    contract = v040_submission_contract()
    assert contract["version"] == "0.4.0"
    assert "implication_provenance" in contract["context_fields"]
    assert "implication_consistency" in contract
