from __future__ import annotations

import copy

import pytest

from epistemic_loop.controller.v043_regression_agent import (
    REGRESSION_SUBMISSION_VERSION,
    RegressionContextArtifact,
    RegressionTranslationPredictions,
    V043RegressionSubmission,
    parse_v043_regression_submission,
    v043_regression_submission_contract,
    validate_v043_regression_submission,
)


def _context(**overrides: object) -> RegressionContextArtifact:
    defaults: dict[str, object] = dict(
        opaque_context_id="ctx-1",
        research_control_stat=-0.2,
        research_structure_stat=0.6,
        independent_implication_strength=0.3,
        control_confirmation_predictions=(500.0, 600.0),
        control_transfer_predictions=(550.0,),
        translations=(
            RegressionTranslationPredictions("cand-a", "kind-a", (510.0, 615.0), (560.0,)),
            RegressionTranslationPredictions("cand-b", "kind-b", (490.0, 585.0), (540.0,)),
        ),
    )
    defaults.update(overrides)
    return RegressionContextArtifact(**defaults)  # type: ignore[arg-type]


def test_translation_predictions_accepts_values_outside_zero_one() -> None:
    translation = RegressionTranslationPredictions("cand-a", "kind-a", (-500.0, 40000.0), (12345.6,))
    assert translation.confirmation_predictions == (-500.0, 40000.0)


def test_translation_predictions_rejects_non_finite_values() -> None:
    with pytest.raises(ValueError, match="finite"):
        RegressionTranslationPredictions("cand-a", "kind-a", (float("nan"),), (1.0,))


def test_context_artifact_accepts_negative_correlation() -> None:
    ctx = _context(research_control_stat=-0.9, research_structure_stat=-0.1)
    assert ctx.research_gain == pytest.approx(0.8)


def test_context_artifact_rejects_stat_outside_unit_interval() -> None:
    with pytest.raises(ValueError, match=r"\[-1,1\]"):
        _context(research_structure_stat=1.5)


def test_context_artifact_rejects_out_of_range_implication_strength() -> None:
    with pytest.raises(ValueError, match="independent implication"):
        _context(independent_implication_strength=1.2)


def _minimal_payload() -> dict:
    return {
        "version": REGRESSION_SUBMISSION_VERSION,
        "suite_id": "v043-regression-suite-01",
        "run_id": "agent-01-s17",
        "agent_id": "agent-01",
        "sampling_seed": 17,
        "prompt_arm": "p1",
        "lineage_policy": "posterior_commit",
        "prompt_hash": "a" * 64,
        "policy_contract_hash": "b" * 64,
        "human_assisted": False,
        "cross_run_information_used": False,
        "artifact_complete": True,
        "oof_honesty_passed": True,
        "hidden_isolation_passed": True,
        "packs": [
            {
                "opaque_pack_id": "pack-1",
                "cycles": [
                    {
                        "cycle": 1,
                        "proposals": [
                            {
                                "mode": mode,
                                "lineage_id": f"lineage-{mode}",
                                "description": "test",
                                "descriptor": {
                                    "hypothesis_family": "f",
                                    "representation_family": "f",
                                    "validation_world": "f",
                                    "observation_unit": "f",
                                    "data_slice": "f",
                                    "experiment_operator": "f",
                                    "model_family": "f",
                                    "downstream_decision": "f",
                                    "structural_claim": False,
                                },
                                "expected_decision": "d",
                                "utility_mean": 0.1,
                                "utility_std": 0.05,
                                "competing_hypotheses": ["h1", "h2"] if mode == "epistemic" else [],
                                "discriminating_observable": "obs" if mode == "epistemic" else None,
                            }
                            for mode in ("exploit", "explore", "epistemic")
                        ],
                        "selected_lineage_id": "lineage-exploit",
                        "selected_mode": "exploit",
                        "decision_changed": False,
                        "performance_improved": False,
                        "uncertainty_reduced": False,
                        "falsification_evidence_added": False,
                        "converted_to_parent_or_final": False,
                        "lineage_followup": False,
                        "lineage_explicitly_closed": False,
                    }
                ],
                "resolution": "falsified",
                "confidence": {
                    "p_structure_exists": 0.2,
                    "p_evidence_sufficient": 0.5,
                    "p_actionable": 0.1,
                    "p_positive_transfer": 0.1,
                },
                "failure_trace": {
                    "hypothesis_generated": True,
                    "discriminating_test_proposed": True,
                    "implementation_completed": True,
                    "support_observed": False,
                    "promotion_passed": False,
                    "above_row_unit_considered": False,
                    "history_or_link_intervention_considered": False,
                },
                "claim": "no structure found",
                "alternatives": ["alt-a", "alt-b"],
                "predicted_true": "x",
                "predicted_false": "y",
                "confounders": [],
                "falsification_conditions": ["cond"],
                "independent_implication": "none",
                "affected_decisions": [],
                "causal_safety_passed": True,
                "leave_one_context_out_stable": False,
                "null_summary": {
                    "replicate_gains": [0.0, 0.01, -0.01, 0.02, -0.02],
                    "all_replicates_refit_features_and_model": True,
                    "preserved_confounders": ["none"],
                    "destroyed_relation": "target",
                    "stopping_reason": "max_replicates",
                },
                "selected_translation_id": "cand-a",
                "shadow_candidate_ids": ["cand-b"],
                "contexts": [
                    {
                        "opaque_context_id": "ctx-1",
                        "research_control_stat": -0.1,
                        "research_structure_stat": 0.05,
                        "independent_implication_strength": 0.1,
                        "control_confirmation_predictions": [500.0, 600.0],
                        "control_transfer_predictions": [550.0],
                        "translations": [
                            {
                                "candidate_id": "cand-a",
                                "translation_kind": "kind-a",
                                "confirmation_predictions": [510.0, 615.0],
                                "transfer_predictions": [560.0],
                            },
                            {
                                "candidate_id": "cand-b",
                                "translation_kind": "kind-b",
                                "confirmation_predictions": [490.0, 585.0],
                                "transfer_predictions": [540.0],
                            },
                        ],
                    },
                    {
                        "opaque_context_id": "ctx-2",
                        "research_control_stat": -0.2,
                        "research_structure_stat": 0.02,
                        "independent_implication_strength": 0.1,
                        "control_confirmation_predictions": [500.0, 600.0],
                        "control_transfer_predictions": [550.0],
                        "translations": [
                            {
                                "candidate_id": "cand-a",
                                "translation_kind": "kind-a",
                                "confirmation_predictions": [505.0, 610.0],
                                "transfer_predictions": [555.0],
                            },
                            {
                                "candidate_id": "cand-b",
                                "translation_kind": "kind-b",
                                "confirmation_predictions": [495.0, 590.0],
                                "transfer_predictions": [545.0],
                            },
                        ],
                    },
                    {
                        "opaque_context_id": "ctx-3",
                        "research_control_stat": -0.15,
                        "research_structure_stat": 0.0,
                        "independent_implication_strength": 0.1,
                        "control_confirmation_predictions": [500.0, 600.0],
                        "control_transfer_predictions": [550.0],
                        "translations": [
                            {
                                "candidate_id": "cand-a",
                                "translation_kind": "kind-a",
                                "confirmation_predictions": [498.0, 601.0],
                                "transfer_predictions": [551.0],
                            },
                            {
                                "candidate_id": "cand-b",
                                "translation_kind": "kind-b",
                                "confirmation_predictions": [502.0, 599.0],
                                "transfer_predictions": [549.0],
                            },
                        ],
                    },
                ],
            }
        ],
    }


def test_parse_v043_regression_submission_round_trips() -> None:
    submission = parse_v043_regression_submission(_minimal_payload())
    assert isinstance(submission, V043RegressionSubmission)
    assert submission.version == REGRESSION_SUBMISSION_VERSION
    assert len(submission.packs) == 1
    assert len(submission.packs[0].contexts) == 3


def test_parse_v043_regression_submission_rejects_wrong_version() -> None:
    payload = copy.deepcopy(_minimal_payload())
    payload["version"] = "0.3.7"
    with pytest.raises(ValueError, match="identity"):
        parse_v043_regression_submission(payload)


def test_validate_v043_regression_submission_reuses_v037_identity_checks() -> None:
    payload = _minimal_payload()
    submission = parse_v043_regression_submission(payload)
    packet = {
        "suite_id": payload["suite_id"],
        "run_id": payload["run_id"],
        "agent_id": payload["agent_id"],
        "sampling_seed": payload["sampling_seed"],
        "prompt_arm": payload["prompt_arm"],
        "prompt_hash": payload["prompt_hash"],
        "policy_contract_hash": payload["policy_contract_hash"],
        "lineage_policy": payload["lineage_policy"],
        "packs": [
            {
                "opaque_pack_id": "pack-1",
                "contexts": [
                    {"opaque_context_id": "ctx-1", "confirmation_rows": 2, "transfer_rows": 1},
                    {"opaque_context_id": "ctx-2", "confirmation_rows": 2, "transfer_rows": 1},
                    {"opaque_context_id": "ctx-3", "confirmation_rows": 2, "transfer_rows": 1},
                ],
            }
        ],
    }
    result = validate_v043_regression_submission(submission, packet)
    assert result.valid, result.errors


def test_contract_describes_correlation_not_probability() -> None:
    contract = v043_regression_submission_contract()
    assert "correlation" in contract["context_fields"]["research_control_stat"]
    assert contract["version"] == REGRESSION_SUBMISSION_VERSION
