import pytest

from epistemic_loop.domain.enums import ValidationSplitType
from epistemic_loop.domain.models import (
    ValidationDiagnostics,
    ValidationOutcomeLikelihood,
    ValidationWorld,
    ValidationWorldEvidence,
    ValidationWorldForecast,
)
from epistemic_loop.validation.worlds import (
    expected_score,
    posterior_entropy,
    rank_reversal_rate,
    spearman_rank_correlation,
    update_worlds,
    validation_fidelity,
)


def _world(identifier: str, split: ValidationSplitType) -> ValidationWorld:
    return ValidationWorld(
        id=identifier,
        run_id="run-001",
        split_type=split,
        assumptions=[f"{split.value} represents hidden test"],
        posterior_probability=1 / 3,
    )


def test_validation_world_posterior_is_bayesian_and_auditable() -> None:
    worlds = [
        _world("W-random", ValidationSplitType.RANDOM),
        _world("W-time", ValidationSplitType.TIME),
        _world("W-group", ValidationSplitType.GROUP),
    ]
    before = posterior_entropy(worlds)
    evidence = ValidationWorldEvidence(
        id="VWE-001",
        run_id="run-001",
        observation_id="OB-001",
        likelihood_by_world={"W-random": 0.1, "W-time": 0.8, "W-group": 0.1},
        metric_name="pseudo_future_rank_accuracy",
        observed_value=0.82,
        preregistration_ref="EXP-001/outcome-rolling-wins",
    )

    updated, event = update_worlds(worlds, evidence)

    posterior = {item.id: item.posterior_probability for item in updated}
    assert posterior == pytest.approx({"W-random": 0.1, "W-time": 0.8, "W-group": 0.1})
    assert event.prior == pytest.approx({item.id: 1 / 3 for item in worlds})
    assert event.evidence_id == evidence.id
    assert posterior_entropy(updated) < before
    assert all(evidence.id in item.evidence_ids for item in updated)


def test_validation_fidelity_renormalizes_over_observed_diagnostics() -> None:
    diagnostics = ValidationDiagnostics(model_rank_stability=1.0, leakage_risk=0.0)
    assert validation_fidelity(diagnostics) == pytest.approx(1.0)
    assert validation_fidelity(ValidationDiagnostics()) is None


def test_expected_score_uses_world_posterior() -> None:
    worlds = [
        ValidationWorld(
            id="W-random",
            run_id="run-001",
            split_type=ValidationSplitType.RANDOM,
            assumptions=["iid"],
            posterior_probability=0.25,
        ),
        ValidationWorld(
            id="W-time",
            run_id="run-001",
            split_type=ValidationSplitType.TIME,
            assumptions=["future"],
            posterior_probability=0.75,
        ),
    ]
    assert expected_score(worlds, {"W-random": 0.9, "W-time": 0.7}) == pytest.approx(0.75)


def test_validation_world_rank_stability_and_reversals() -> None:
    random_scores = {"linear": 0.7, "gbdt": 0.9, "neural": 0.8}
    time_scores = {"linear": 0.9, "gbdt": 0.7, "neural": 0.8}
    assert spearman_rank_correlation(random_scores, time_scores) == pytest.approx(-1.0)
    assert rank_reversal_rate(random_scores, time_scores) == pytest.approx(1.0)


def test_validation_world_forecast_requires_normalized_world_vectors() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="must sum to 1"):
        ValidationWorldForecast(
            outcomes=[
                ValidationOutcomeLikelihood(label="time_wins", probability_by_world={"W-random": 0.2, "W-time": 0.8}),
                ValidationOutcomeLikelihood(label="random_wins", probability_by_world={"W-random": 0.7, "W-time": 0.2}),
            ],
            metric_name="rank_stability",
            decisions_affected=["primary_validation"],
            measurement_notes="same candidates and seeds",
        )
