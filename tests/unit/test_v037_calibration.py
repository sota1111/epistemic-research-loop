from epistemic_loop.evaluation.calibration_v037 import (
    calibration_adjusted_evidence_gate,
    fit_development_isotonic_map,
)


def test_development_calibration_is_monotone() -> None:
    mapping = fit_development_isotonic_map(
        (0.05, 0.15, 0.25, 0.35, 0.65, 0.75, 0.85, 0.95),
        (False, False, True, False, True, False, True, True),
    )
    calibrated = [mapping.apply(index / 20) for index in range(21)]
    assert calibrated == sorted(calibrated)
    assert mapping.training_samples == 8


def test_bad_development_calibration_increases_evidence_not_bans_agent() -> None:
    baseline = calibration_adjusted_evidence_gate(0.10)
    escalated = calibration_adjusted_evidence_gate(0.34)
    severe = calibration_adjusted_evidence_gate(0.50)
    assert baseline.minimum_full_refit_null_replicates == 5
    assert escalated.minimum_supporting_contexts == 3
    assert severe.minimum_full_refit_null_replicates == 20
