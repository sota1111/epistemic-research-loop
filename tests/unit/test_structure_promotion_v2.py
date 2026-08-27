from __future__ import annotations

from epistemic_loop.controller.structure_validation import (
    ControlFamilyRole,
    SeedEvidenceDisposition,
    SeedStructureEvidence,
    StructureControlFamilyResult,
    StructurePromotionGateV2,
)
from epistemic_loop.domain.enums import StructureLifecycleState


def _evidence(*dispositions: SeedEvidenceDisposition) -> tuple[SeedStructureEvidence, ...]:
    return tuple(SeedStructureEvidence(seed, disposition) for seed, disposition in enumerate(dispositions))


def _controls() -> tuple[StructureControlFamilyResult, ...]:
    return (
        StructureControlFamilyResult("tuning-entity", ControlFamilyRole.THRESHOLD_TUNING, True, True),
        StructureControlFamilyResult("held-temporal", ControlFamilyRole.HELD_OUT_EVALUATION, True, True),
        StructureControlFamilyResult("held-random-link", ControlFamilyRole.HELD_OUT_EVALUATION, False, False),
    )


def test_terminal_promotion_is_aggregate_only_and_leave_one_seed_out_stable() -> None:
    decision = StructurePromotionGateV2().assess(
        _evidence(*([SeedEvidenceDisposition.SUPPORTING_EVIDENCE] * 3)),
        _controls(),
    )

    assert decision.promoted
    assert decision.lifecycle_state is StructureLifecycleState.VALIDATED_STRUCTURE
    assert all(item.passed for item in decision.leave_one_seed_out)


def test_one_contradicting_seed_prevents_unstable_promotion() -> None:
    decision = StructurePromotionGateV2().assess(
        _evidence(
            SeedEvidenceDisposition.SUPPORTING_EVIDENCE,
            SeedEvidenceDisposition.SUPPORTING_EVIDENCE,
            SeedEvidenceDisposition.CONTRADICTING_EVIDENCE,
        ),
        _controls(),
    )

    assert not decision.promoted
    assert decision.lifecycle_state is StructureLifecycleState.INCONCLUSIVE
    assert "full_seed_aggregate_failed" in decision.reasons
    assert "leave_one_seed_out_unstable" in decision.reasons


def test_held_out_control_false_promotion_blocks_structure() -> None:
    controls = list(_controls())
    controls[-1] = StructureControlFamilyResult(
        "held-random-link", ControlFamilyRole.HELD_OUT_EVALUATION, False, True
    )
    decision = StructurePromotionGateV2().assess(
        _evidence(*([SeedEvidenceDisposition.SUPPORTING_EVIDENCE] * 3)),
        controls,
    )

    assert not decision.promoted
    assert "held_out_negative_control_false_promotion" in decision.reasons


def test_tuning_family_cannot_be_reused_as_held_out() -> None:
    controls = (
        StructureControlFamilyResult("same", ControlFamilyRole.THRESHOLD_TUNING, True, True),
        StructureControlFamilyResult("same", ControlFamilyRole.HELD_OUT_EVALUATION, True, True),
        StructureControlFamilyResult("negative", ControlFamilyRole.HELD_OUT_EVALUATION, False, False),
    )
    decision = StructurePromotionGateV2().assess(
        _evidence(*([SeedEvidenceDisposition.SUPPORTING_EVIDENCE] * 3)), controls
    )

    assert "control_family_reused_after_threshold_tuning" in decision.reasons
