import pytest
from pydantic import ValidationError

from epistemic_loop.domain.models import Hypothesis


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
