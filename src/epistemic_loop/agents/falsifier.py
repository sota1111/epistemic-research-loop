from __future__ import annotations

import uuid

from epistemic_loop.domain.enums import FalsificationDisposition
from epistemic_loop.domain.models import FalsificationRecord, Hypothesis, Observation


class Falsifier:
    def record(
        self,
        hypothesis: Hypothesis,
        observations: list[Observation],
        *,
        supporting_predictions: list[str],
        contradicting_predictions: list[str],
        alternative_explanation: str,
        confounders_checked: list[str],
        recommended_next_test: str | None = None,
        alternative_claims: list[str] | None = None,
    ) -> FalsificationRecord:
        if not observations:
            raise ValueError("falsification requires at least one observation")
        if contradicting_predictions and not supporting_predictions:
            disposition = FalsificationDisposition.FALSIFIED
        elif contradicting_predictions:
            disposition = FalsificationDisposition.WEAKENED
        elif supporting_predictions and confounders_checked:
            disposition = FalsificationDisposition.SURVIVES
        else:
            disposition = FalsificationDisposition.INCONCLUSIVE
        return FalsificationRecord(
            id=f"FR-{uuid.uuid4().hex[:12]}",
            hypothesis_id=hypothesis.id,
            observation_ids=[item.id for item in observations],
            strongest_alternative_explanation=alternative_explanation,
            confounders_checked=confounders_checked,
            supporting_predictions_matched=supporting_predictions,
            contradicting_predictions_matched=contradicting_predictions,
            disposition=disposition,
            recommended_next_test=recommended_next_test,
            alternative_claims=list(alternative_claims or []),
        )
