import pytest

from epistemic_loop.belief.calibration import summarize_calibration
from epistemic_loop.controller.allocation import adaptive_allocation
from epistemic_loop.domain.enums import RunMode
from epistemic_loop.domain.models import ForecastCalibrationRecord, HypothesisOutcomeForecast, OutcomeLikelihood
from epistemic_loop.scoring.epistemic import (
    binary_hypothesis_information_gain,
    monte_carlo_binary_information_gain,
)


def _forecast() -> HypothesisOutcomeForecast:
    return HypothesisOutcomeForecast(
        hypothesis_id="H-1",
        outcomes=[
            OutcomeLikelihood(label="yes", probability_if_true=0.9, probability_if_false=0.2),
            OutcomeLikelihood(label="no", probability_if_true=0.1, probability_if_false=0.8),
        ],
        decisions_affected=["validation"],
        measurement_notes="fixed categorical likelihood",
    )


def test_seeded_monte_carlo_eig_approximates_exact_mutual_information() -> None:
    forecast = _forecast()
    exact = binary_hypothesis_information_gain(0.6, forecast)
    first = monte_carlo_binary_information_gain(0.6, forecast, samples=30_000, seed=7)
    second = monte_carlo_binary_information_gain(0.6, forecast, samples=30_000, seed=7)

    assert first == second
    assert first == pytest.approx(exact, abs=0.01)


def test_calibration_summary_reports_confidence_and_interval_coverage() -> None:
    records = [
        ForecastCalibrationRecord(
            id="F-1",
            run_id="run",
            experiment_id="E-1",
            proposer_agent="agent",
            category="validation",
            probabilities={"yes": 0.8, "no": 0.2},
            observed_label="yes",
            interval_coverage={"0.5": True, "0.8": True},
        ),
        ForecastCalibrationRecord(
            id="F-2",
            run_id="run",
            experiment_id="E-2",
            proposer_agent="agent",
            category="validation",
            probabilities={"yes": 0.7, "no": 0.3},
            observed_label="no",
            interval_coverage={"0.5": False, "0.8": True},
        ),
    ]
    summary = summarize_calibration(records)

    assert summary.count == 2
    assert summary.accuracy == 0.5
    assert summary.overconfidence_rate == 0.5
    assert summary.interval_coverage_50 == 0.5
    assert summary.interval_coverage_80 == 1.0
    assert summary.interval_coverage_95 is None


def test_preferred_state_gap_modulates_but_does_not_break_epistemic_allocation() -> None:
    base = {"exploit": 0.4, "qd_explore": 0.3, "epistemic": 0.3}
    near = adaptive_allocation(base, mode=RunMode.SYSTEM_C, qd_occupancy=1, preferred_state_gap=0.0)
    far = adaptive_allocation(base, mode=RunMode.SYSTEM_C, qd_occupancy=1, preferred_state_gap=1.0)

    assert far["epistemic"] > near["epistemic"] > base["epistemic"]
    assert sum(far.values()) == pytest.approx(1.0)
