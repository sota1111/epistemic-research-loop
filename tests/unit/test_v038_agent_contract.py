from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

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
    adjudicated_failure_trace,
    load_v038_submission,
    v038_submission_contract,
    validate_v038_submission,
)


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _replicate(index: int, gain: float) -> dict[str, Any]:
    return {
        "replicate_index": index,
        "permutation_hash": _digest(f"permutation-{index}"),
        "preserved_statistics": {"frequency_mean": 0.5, "time_span": 1.0},
        "feature_manifest_hash": _digest(f"features-{index}"),
        "fold_plan_hash": _digest(f"folds-{index}"),
        "model_fit_manifest_hash": _digest(f"model-{index}"),
        "oof_prediction_hash": _digest(f"oof-{index}"),
        "gain": gain,
    }


def _proposal(mode: V037ResearchMode, suffix: str, structural: bool = True) -> V037Proposal:
    return V037Proposal(
        mode=mode,
        lineage_id=f"{suffix}-{mode.value}",
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
            structural_claim=structural and mode is V037ResearchMode.EPISTEMIC,
        ),
        expected_decision="retain or reject",
        utility_mean=0.5,
        utility_std=0.1,
        competing_hypotheses=("linked", "artifact") if mode is V037ResearchMode.EPISTEMIC else (),
        discriminating_observable="refit-null gain" if mode is V037ResearchMode.EPISTEMIC else None,
    )


def _cycle(number: int, suffix: str, *, closed: bool = True) -> V037CycleRecord:
    return V037CycleRecord(
        cycle=number,
        proposals=tuple(_proposal(mode, suffix) for mode in V037ResearchMode),
        selected_lineage_id=f"{suffix}-epistemic",
        selected_mode=V037ResearchMode.EPISTEMIC,
        decision_changed=True,
        performance_improved=False,
        uncertainty_reduced=True,
        falsification_evidence_added=False,
        converted_to_parent_or_final=False,
        lineage_followup=False,
        lineage_explicitly_closed=closed,
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


def _pack(*, cycles: tuple[V037CycleRecord, ...] | None = None) -> V037PackSubmission:
    return V037PackSubmission(
        opaque_pack_id="opaque-pack",
        cycles=cycles if cycles is not None else (_cycle(1, "lineage"),),
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


def _payload(pack: V037PackSubmission, policy: LineagePolicy) -> dict[str, Any]:
    submission = V037AgentSubmission(
        version="0.3.7",
        suite_id="v038-qual-c01",
        run_id="agent-01-s17",
        agent_id="agent-01",
        sampling_seed=17,
        prompt_arm="p1",
        lineage_policy=policy,
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
    payload["version"] = "0.3.8"
    payload["lineage_policy"] = policy.value
    for raw_pack, source in zip(payload["packs"], submission.packs, strict=True):
        raw_pack["resolution"] = source.resolution.value
        raw_pack["null_summary"]["stopping_reason"] = source.null_summary.stopping_reason.value
        raw_pack["null_summary"]["replicates"] = [
            _replicate(index + 1, gain) for index, gain in enumerate(source.null_summary.replicate_gains)
        ]
        for cycle_raw, cycle in zip(raw_pack["cycles"], source.cycles, strict=True):
            cycle_raw["selected_mode"] = cycle.selected_mode.value
            for proposal_raw, proposal in zip(cycle_raw["proposals"], cycle.proposals, strict=True):
                proposal_raw["mode"] = proposal.mode.value
    return payload


def _packet(policy: LineagePolicy) -> dict[str, Any]:
    return {
        "version": "0.3.8",
        "suite_id": "v038-qual-c01",
        "run_id": "agent-01-s17",
        "agent_id": "agent-01",
        "sampling_seed": 17,
        "prompt_arm": "p1",
        "prompt_hash": "hash",
        "policy_contract_hash": "policy",
        "lineage_policy": policy.value,
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


def _write(tmp_path: Path, payload: dict[str, Any]) -> Path:
    path = tmp_path / "agent_submission.json"
    path.write_text(json.dumps(payload))
    return path


def test_v038_contract_accepts_complete_provenance(tmp_path: Path) -> None:
    payload = _payload(_pack(), LineagePolicy.DETERMINISTIC_BEST)
    loaded = load_v038_submission(_write(tmp_path, payload))
    assert loaded.extras.declared_version == "0.3.8"
    assert len(loaded.extras.provenance["opaque-pack"]) == 5
    validation = validate_v038_submission(loaded, _packet(LineagePolicy.DETERMINISTIC_BEST))
    assert validation.valid, validation.errors


def test_v038_rejects_wrong_version(tmp_path: Path) -> None:
    payload = _payload(_pack(), LineagePolicy.DETERMINISTIC_BEST)
    payload["version"] = "0.3.7"
    with pytest.raises(ValueError, match="v0.3.8"):
        load_v038_submission(_write(tmp_path, payload))


def test_v038_rejects_incomplete_or_copied_provenance(tmp_path: Path) -> None:
    missing = _payload(_pack(), LineagePolicy.DETERMINISTIC_BEST)
    missing["packs"][0]["null_summary"]["replicates"] = missing["packs"][0]["null_summary"]["replicates"][:3]
    loaded = load_v038_submission(_write(tmp_path, missing))
    errors = validate_v038_submission(loaded, _packet(LineagePolicy.DETERMINISTIC_BEST)).errors
    assert any("replicate count" in item for item in errors)

    copied = _payload(_pack(), LineagePolicy.DETERMINISTIC_BEST)
    for replicate in copied["packs"][0]["null_summary"]["replicates"]:
        replicate["oof_prediction_hash"] = _digest("oof-shared")
    loaded = load_v038_submission(_write(tmp_path, copied))
    errors = validate_v038_submission(loaded, _packet(LineagePolicy.DETERMINISTIC_BEST)).errors
    assert any("oof_prediction_hash" in item for item in errors)

    drifted = _payload(_pack(), LineagePolicy.DETERMINISTIC_BEST)
    drifted["packs"][0]["null_summary"]["replicates"][0]["gain"] = 0.5
    loaded = load_v038_submission(_write(tmp_path, drifted))
    errors = validate_v038_submission(loaded, _packet(LineagePolicy.DETERMINISTIC_BEST)).errors
    assert any("does not match declared" in item for item in errors)


def test_v038_lineage_continuity_is_enforced_for_deep_policies(tmp_path: Path) -> None:
    abandoned = _pack(cycles=(_cycle(1, "first", closed=False), _cycle(2, "second")))
    payload = _payload(abandoned, LineagePolicy.POSTERIOR_COMMIT)
    loaded = load_v038_submission(_write(tmp_path, payload))
    errors = validate_v038_submission(loaded, _packet(LineagePolicy.POSTERIOR_COMMIT)).errors
    assert any("abandoned open lineage" in item for item in errors)

    followed = _pack(cycles=(_cycle(1, "first", closed=True), _cycle(2, "second")))
    payload = _payload(followed, LineagePolicy.POSTERIOR_COMMIT)
    loaded = load_v038_submission(_write(tmp_path, payload))
    assert validate_v038_submission(loaded, _packet(LineagePolicy.POSTERIOR_COMMIT)).valid

    shallow = _payload(abandoned, LineagePolicy.DETERMINISTIC_BEST)
    loaded = load_v038_submission(_write(tmp_path, shallow))
    assert validate_v038_submission(loaded, _packet(LineagePolicy.DETERMINISTIC_BEST)).valid


def test_v038_adjudicates_failure_stages_from_artifacts() -> None:
    pack = _pack()
    stages = adjudicated_failure_trace(pack)
    assert stages == {
        "hypothesis_generated": True,
        "discriminating_test_proposed": True,
        "implementation_completed": True,
    }
    non_structural = V037PackSubmission(
        **{
            **{field: getattr(pack, field) for field in pack.__dataclass_fields__},
            "cycles": (
                V037CycleRecord(
                    cycle=1,
                    proposals=tuple(_proposal(mode, "plain", structural=False) for mode in V037ResearchMode),
                    selected_lineage_id="plain-epistemic",
                    selected_mode=V037ResearchMode.EPISTEMIC,
                    decision_changed=False,
                    performance_improved=False,
                    uncertainty_reduced=True,
                    falsification_evidence_added=False,
                    converted_to_parent_or_final=False,
                    lineage_followup=False,
                    lineage_explicitly_closed=True,
                ),
            ),
        }
    )
    assert not adjudicated_failure_trace(non_structural)["hypothesis_generated"]


def test_v038_contract_documents_the_additions() -> None:
    contract = v038_submission_contract()
    assert contract["version"] == "0.3.8"
    assert "replicates" in contract["null_summary"]
    assert "null_replicate_fields" in contract
    assert "lineage_continuity_rule" in contract
