from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet

from epistemic_loop.benchmark.v039_repro_suite import (
    V039_QUAL_SUITE_IDS,
    V039_RUN_IDS,
    build_v039_suite,
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
from epistemic_loop.controller.v039_agent import (
    load_v039_submission,
    v039_submission_contract,
    validate_v039_submission,
)


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


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


def _context(index: int, *, implication: float, structure_auc: float = 0.62) -> V037ContextArtifact:
    translations = tuple(
        TranslationPredictions(candidate, kind, (0.2, 0.8), (0.3, 0.7))
        for candidate, kind in (("translation-a", "history"), ("translation-b", "routing"))
    )
    return V037ContextArtifact(
        opaque_context_id=f"context-{index}",
        research_control_auc=0.6,
        research_structure_auc=structure_auc,
        independent_implication_strength=implication,
        control_confirmation_predictions=(0.4, 0.6),
        control_transfer_predictions=(0.4, 0.6),
        translations=translations,
    )


def _pack(resolution: V037Resolution, *, implication: float, structure_auc: float = 0.62) -> V037PackSubmission:
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
        contexts=tuple(_context(index, implication=implication, structure_auc=structure_auc) for index in range(3)),
    )


def _payload(pack: V037PackSubmission) -> dict[str, Any]:
    submission = V037AgentSubmission(
        version="0.3.7",
        suite_id="v039-qual-e01",
        run_id="agent-01-s17",
        agent_id="agent-01",
        sampling_seed=17,
        prompt_arm="p1",
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
    payload = asdict(submission)
    payload["version"] = "0.3.9"
    for raw_pack, source in zip(payload["packs"], submission.packs, strict=True):
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
            for index, gain in enumerate(source.null_summary.replicate_gains)
        ]
    return payload


def _packet() -> dict[str, Any]:
    return {
        "version": "0.3.9",
        "suite_id": "v039-qual-e01",
        "run_id": "agent-01-s17",
        "agent_id": "agent-01",
        "sampling_seed": 17,
        "prompt_arm": "p1",
        "prompt_hash": "hash",
        "policy_contract_hash": "policy",
        "lineage_policy": "deterministic_best",
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
    return load_v039_submission(path)


def test_v039_falsified_with_high_implication_is_rejected(tmp_path: Path) -> None:
    inconsistent = _load(tmp_path, _payload(_pack(V037Resolution.FALSIFIED, implication=0.3)))
    errors = validate_v039_submission(inconsistent, _packet()).errors
    assert any("falsified resolution conflicts" in item and "implication" in item for item in errors)

    consistent = _load(tmp_path, _payload(_pack(V037Resolution.FALSIFIED, implication=0.0, structure_auc=0.6)))
    validation = validate_v039_submission(consistent, _packet())
    assert validation.valid, validation.errors


def test_v039_falsified_with_research_gain_above_own_null_is_rejected(tmp_path: Path) -> None:
    loaded = _load(tmp_path, _payload(_pack(V037Resolution.FALSIFIED, implication=0.0, structure_auc=0.75)))
    errors = validate_v039_submission(loaded, _packet()).errors
    assert any("full-refit null 95th percentile" in item for item in errors)


def test_v039_validated_requires_implication_support(tmp_path: Path) -> None:
    weak = _load(tmp_path, _payload(_pack(V037Resolution.VALIDATED_NON_ACTIONABLE, implication=0.01)))
    errors = validate_v039_submission(weak, _packet()).errors
    assert any("validated structure requires" in item for item in errors)

    strong = _load(tmp_path, _payload(_pack(V037Resolution.VALIDATED_NON_ACTIONABLE, implication=0.4)))
    assert validate_v039_submission(strong, _packet()).valid


def test_v039_inconclusive_is_not_constrained(tmp_path: Path) -> None:
    loaded = _load(tmp_path, _payload(_pack(V037Resolution.INCONCLUSIVE, implication=0.3, structure_auc=0.75)))
    assert validate_v039_submission(loaded, _packet()).valid


def test_v039_load_rejects_other_versions(tmp_path: Path) -> None:
    payload = _payload(_pack(V037Resolution.INCONCLUSIVE, implication=0.0))
    payload["version"] = "0.3.8"
    path = tmp_path / "agent_submission.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="v0.3.9"):
        load_v039_submission(path)


def test_v039_contract_documents_consistency_rule() -> None:
    contract = v039_submission_contract()
    assert contract["version"] == "0.3.9"
    assert "terminal_resolution_consistency" in contract


def test_v039_suite_build_uses_new_identity_and_same_design(tmp_path: Path) -> None:
    key = Fernet.generate_key()
    prompt = tmp_path / "p1.md"
    prompt.write_text("challenge prompt\n")
    contract = {
        "null_policy": {"minimum": 5, "maximum": 30, "provenance_required": True},
        "confidence_fields": ["p_structure_exists"],
    }
    result = build_v039_suite(
        suite_id=V039_QUAL_SUITE_IDS[0],
        output_root=tmp_path / "public" / V039_QUAL_SUITE_IDS[0],
        truth_root=tmp_path / "truth",
        key=key,
        prompt_path=prompt,
        policy_contract=contract,
        rows_per_context=600,
    )
    assert result.preflight_passed
    packet = json.loads(
        (
            tmp_path / "public" / V039_QUAL_SUITE_IDS[0] / "agent_views" / V039_RUN_IDS[0] / "agent_packet.json"
        ).read_text()
    )
    assert packet["version"] == "0.3.9"
    assert packet["prompt_arm"] == "p1"
    with pytest.raises(ValueError, match="preregistered"):
        build_v039_suite(
            suite_id="v038-qual-c01",
            output_root=tmp_path / "public" / "x",
            truth_root=tmp_path / "truth",
            key=key,
            prompt_path=prompt,
            policy_contract=contract,
            rows_per_context=600,
        )


def test_v039_replace_keeps_core_reusable() -> None:
    pack = _pack(V037Resolution.INCONCLUSIVE, implication=0.0)
    assert replace(pack, resolution=V037Resolution.FALSIFIED).resolution is V037Resolution.FALSIFIED
