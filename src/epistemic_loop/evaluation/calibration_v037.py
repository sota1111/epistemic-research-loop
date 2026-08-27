"""Development-only confidence calibration and evidence escalation for v0.3.7."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IsotonicCalibrationMap:
    upper_bounds: tuple[float, ...]
    calibrated_values: tuple[float, ...]
    training_samples: int

    def __post_init__(self) -> None:
        if not self.upper_bounds or len(self.upper_bounds) != len(self.calibrated_values):
            raise ValueError("calibration map requires aligned non-empty blocks")
        if tuple(sorted(self.upper_bounds)) != self.upper_bounds:
            raise ValueError("calibration bounds must be ordered")
        if any(not 0 <= value <= 1 for value in self.calibrated_values):
            raise ValueError("calibrated probabilities must lie in [0,1]")

    def apply(self, probability: float) -> float:
        if not 0 <= probability <= 1:
            raise ValueError("raw probability must lie in [0,1]")
        for upper, value in zip(self.upper_bounds, self.calibrated_values, strict=True):
            if probability <= upper:
                return value
        return self.calibrated_values[-1]


@dataclass(frozen=True)
class CalibrationAdjustedEvidenceGate:
    minimum_supporting_contexts: int
    minimum_full_refit_null_replicates: int
    leave_one_context_out_required: bool


def fit_development_isotonic_map(
    probabilities: tuple[float, ...],
    outcomes: tuple[bool, ...],
) -> IsotonicCalibrationMap:
    """Fit a monotone map using development truth only via pool-adjacent violators."""

    if len(probabilities) != len(outcomes) or len(probabilities) < 8:
        raise ValueError("development calibration requires at least eight aligned observations")
    if any(not 0 <= value <= 1 for value in probabilities):
        raise ValueError("raw development probabilities must lie in [0,1]")
    ordered = sorted(zip(probabilities, outcomes, strict=True), key=lambda item: item[0])
    blocks: list[list[float]] = []
    for probability, outcome in ordered:
        blocks.append([probability, probability, float(outcome), 1.0])
        while len(blocks) >= 2:
            previous = blocks[-2][2] / blocks[-2][3]
            current = blocks[-1][2] / blocks[-1][3]
            if previous <= current:
                break
            right = blocks.pop()
            left = blocks.pop()
            blocks.append([left[0], right[1], left[2] + right[2], left[3] + right[3]])
    return IsotonicCalibrationMap(
        upper_bounds=tuple(block[1] for block in blocks),
        calibrated_values=tuple(block[2] / block[3] for block in blocks),
        training_samples=len(probabilities),
    )


def calibration_adjusted_evidence_gate(development_ece: float) -> CalibrationAdjustedEvidenceGate:
    """Increase evidence requirements without automatically banning a poorly calibrated agent."""

    if not 0 <= development_ece <= 1:
        raise ValueError("development ECE must lie in [0,1]")
    if development_ece <= 0.20:
        return CalibrationAdjustedEvidenceGate(2, 5, True)
    if development_ece <= 0.35:
        return CalibrationAdjustedEvidenceGate(3, 10, True)
    return CalibrationAdjustedEvidenceGate(3, 20, True)
