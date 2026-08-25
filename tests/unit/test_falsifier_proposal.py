import pytest

from epistemic_loop.agents.falsifier import Falsifier
from epistemic_loop.domain.models import Hypothesis


def test_independent_falsifier_generates_a_minimal_counter_experiment(hypothesis: Hypothesis) -> None:
    target = hypothesis.model_copy(
        update={
            "alternative_hypothesis_ids": ["H-GROUP"],
            "current_confidence": 0.85,
            "version": 2,
            "created_by": "validation-scientist",
        }
    )
    proposal = Falsifier().propose(
        [target],
        available_data=["train", "timestamp"],
        remaining_cpu_hours=0.5,
    )
    assert proposal.target_hypothesis == target.id
    assert proposal.alternative_hypothesis_id == "H-GROUP"
    assert proposal.estimated_cpu_hours == 0.5
    assert "rationale" not in proposal.context_fields
    assert "created_by" not in proposal.context_fields

    with pytest.raises(ValueError, match="must not be the agent"):
        Falsifier().propose(
            [target],
            available_data=["train"],
            remaining_cpu_hours=1,
            proposer_agent="validation-scientist",
        )
