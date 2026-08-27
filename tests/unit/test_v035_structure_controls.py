from __future__ import annotations

import inspect

import pytest

from epistemic_loop.benchmark.structure_controls_v035 import (
    CONTROL_SEEDS,
    AgentControlView,
    GenericBlindStructureAgent,
    generate_blind_structure_controls,
)
from epistemic_loop.evaluation.v035 import (
    QualificationReliability,
    SeedControlObservation,
    StructureQualificationReport,
    StructureValidationBundle,
)


def _observation(
    control_id: str,
    seed: int,
    *,
    present: bool,
    supporting: bool,
    gain: float,
) -> SeedControlObservation:
    return SeedControlObservation(
        control_id=control_id,
        seed=seed,
        structure_present=present,
        predicted_structure_probability=0.85 if supporting else 0.15,
        selected_operator="generic-operator",
        ground_truth_operator_match=present,
        bundle=StructureValidationBundle(
            competing_hypotheses_registered=True,
            fold_causal_safety=True,
            confounder_preserving_null=supporting,
            independent_implication=supporting,
            multi_context_replication=supporting,
            negative_control_discrimination=supporting,
            decision_changed=supporting,
        ),
        structure_free_sealed_auc=0.70,
        structure_informed_sealed_auc=0.70 + gain,
    )


def test_structure_promotion_is_aggregate_only_and_leave_one_seed_out_stable() -> None:
    observations = [
        _observation("positive", seed, present=True, supporting=True, gain=0.03) for seed in CONTROL_SEEDS
    ] + [_observation("negative", seed, present=False, supporting=False, gain=0.0) for seed in CONTROL_SEEDS]
    report = StructureQualificationReport.evaluate(observations)
    positive = next(item for item in report.families if item.control_id == "positive")

    assert positive.promoted
    assert all(item.promoted for item in positive.leave_one_seed_out)
    assert report.true_structure_discovery_rate == 1.0
    assert report.true_structure_rejection_rate == 1.0
    assert report.false_structure_promotion_rate == 0.0
    assert report.useful_structure_transfer_rate == 1.0


def test_one_supporting_seed_cannot_promote_a_structure() -> None:
    observations = [
        _observation("positive", seed, present=True, supporting=seed == CONTROL_SEEDS[0], gain=0.03)
        for seed in CONTROL_SEEDS
    ] + [_observation("negative", seed, present=False, supporting=False, gain=0.0) for seed in CONTROL_SEEDS]
    report = StructureQualificationReport.evaluate(observations)
    positive = next(item for item in report.families if item.control_id == "positive")
    assert not positive.promoted
    assert report.true_structure_discovery_rate == 0.0


def test_agent_api_cannot_receive_controller_truth() -> None:
    parameters = inspect.signature(GenericBlindStructureAgent.investigate).parameters
    assert "view" in parameters
    assert "control" not in parameters
    assert "generator_seed" not in AgentControlView.__dataclass_fields__
    control = generate_blind_structure_controls(seeds=CONTROL_SEEDS, rows=300)[0]
    assert control.view.opaque_case_id.startswith("case-")
    assert all(row.target == -1 for row in control.view.sealed_rows)


def test_reliability_requires_exact_contract_honesty_and_isolation() -> None:
    assert QualificationReliability(1.0, 1.0, 1.0).passed
    assert not QualificationReliability(1.0, 0.99, 1.0).passed


def test_control_generator_requires_three_seeds() -> None:
    with pytest.raises(ValueError, match="three unique seeds"):
        generate_blind_structure_controls(seeds=(1, 2), rows=300)
