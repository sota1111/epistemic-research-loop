import pytest
from pydantic import ValidationError

from epistemic_loop.domain.models import Hypothesis, HypothesisOutcomeForecast, OutcomeLikelihood


def test_hypothesis_requires_true_and_false_predictions(hypothesis: Hypothesis) -> None:
    payload = hypothesis.model_dump()
    payload["predictions_if_false"] = []
    with pytest.raises(ValidationError):
        Hypothesis.model_validate(payload)


def test_initial_confidence_cannot_be_changed_post_hoc(hypothesis: Hypothesis) -> None:
    payload = hypothesis.model_dump()
    payload["current_confidence"] = 0.8
    with pytest.raises(ValidationError, match="version 1"):
        Hypothesis.model_validate(payload)


def test_outcome_forecast_requires_two_probability_vectors() -> None:
    forecast = HypothesisOutcomeForecast(
        hypothesis_id="H-001",
        outcomes=[
            OutcomeLikelihood(label="large_gap", probability_if_true=0.8, probability_if_false=0.1),
            OutcomeLikelihood(label="small_gap", probability_if_true=0.2, probability_if_false=0.9),
        ],
        decisions_affected=["choose time or random validation"],
        measurement_notes="two fixed seeds; bootstrap uncertainty reported",
    )
    assert sum(item.probability_if_true for item in forecast.outcomes) == 1

    payload = forecast.model_dump()
    payload["outcomes"][0]["probability_if_true"] = 0.7
    with pytest.raises(ValidationError, match="sum to 1"):
        HypothesisOutcomeForecast.model_validate(payload)


def test_the_observer_carries_the_environment_through_untouched() -> None:
    """A designer has to write a command that runs, so it needs facts, not only beliefs.

    Everything else the observer produces is an interpretation of the competition. The environment
    is not: it is where the data sits and what runner exists. Dropping it is how an unattended run
    invents `data/train_transaction.csv` and fails on a missing file.
    """
    from epistemic_loop.agents.observer import CompetitionObserver

    world = CompetitionObserver().observe(
        {
            "metric": {"name": "roc_auc"},
            "target": {"name": "isFraud"},
            "columns": ["TransactionDT", "card1", "isFraud"],
            "row_counts": {"train": 590540},
            "solver_interface": {"entry_point": "python3 src/solver/experiment.py", "usage": "--mode train ..."},
            "data_layout": {"train": ".data/parquet/train.parquet"},
            "notes": ["V columns are undocumented"],
            "irrelevant_key": "dropped",
        }
    )

    assert world.environment["solver_interface"]["entry_point"] == "python3 src/solver/experiment.py"
    assert world.environment["data_layout"] == {"train": ".data/parquet/train.parquet"}
    assert world.environment["columns"] == ["TransactionDT", "card1", "isFraud"]
    assert world.environment["row_counts"] == {"train": 590540}
    assert "irrelevant_key" not in world.environment, "only the named environment keys travel"

    # The interpretive fields still say what is unresolved rather than asserting facts.
    assert any("unresolved" in item for item in world.train_test_shift)
