from __future__ import annotations

import uuid
from collections.abc import Sequence

from epistemic_loop.domain.enums import Consequence, FalsificationDisposition
from epistemic_loop.domain.models import FalsificationProposal, FalsificationRecord, Hypothesis, Observation

_DECISION_IMPACT = {
    Consequence.LOW: 0.25,
    Consequence.MEDIUM: 0.5,
    Consequence.HIGH: 0.75,
    Consequence.CRITICAL: 1.0,
}


class Falsifier:
    @staticmethod
    def priority(hypothesis: Hypothesis) -> float:
        decision_impact = _DECISION_IMPACT[hypothesis.downstream_consequence]
        overconfidence_risk = max(0.1, 2 * abs(hypothesis.current_confidence - 0.5))
        falsifiability = min(
            1.0,
            0.25 * len(hypothesis.falsification_requirements) + 0.25 * len(hypothesis.predictions_if_false),
        )
        return hypothesis.current_confidence * decision_impact * overconfidence_risk * falsifiability

    def propose(
        self,
        hypotheses: Sequence[Hypothesis],
        *,
        available_data: Sequence[str],
        remaining_cpu_hours: float,
        proposer_agent: str = "independent-falsifier",
    ) -> FalsificationProposal:
        """Generate the cheapest explicit attack on the highest-impact belief.

        Only registry fields named in ``context_fields`` influence this method;
        rationale, prompt history, and the originating agent's reasoning are not
        passed through. This is the enforceable part of independent context.
        """

        eligible = [
            item
            for item in hypotheses
            if item.falsification_requirements and item.predictions_if_false and item.current_confidence >= 0.5
        ]
        if not eligible:
            raise ValueError("no supported, falsifiable hypothesis is available")
        target = max(eligible, key=lambda item: (self.priority(item), item.id))
        if proposer_agent == target.created_by:
            raise ValueError("the falsifier must not be the agent that proposed the target hypothesis")
        if remaining_cpu_hours <= 0:
            raise ValueError("no CPU budget remains for a falsification experiment")

        prediction = target.predictions_if_false[0]
        requirement = target.falsification_requirements[0]
        data_note = f" using available data: {', '.join(sorted(available_data))}" if available_data else ""
        attack = [target.type.value, *target.falsification_requirements[:2]]
        return FalsificationProposal(
            id=f"FP-{uuid.uuid4().hex[:12]}",
            target_hypothesis=target.id,
            priority=self.priority(target),
            attack_surface=attack,
            minimal_experiment=f"{requirement}{data_note}",
            estimated_cpu_hours=min(1.0, remaining_cpu_hours),
            falsification_metric=prediction.metric_name,
            falsification_condition=prediction.description,
            alternative_hypothesis_id=(
                target.alternative_hypothesis_ids[0] if target.alternative_hypothesis_ids else None
            ),
            context_fields=[
                "claim",
                "current_confidence",
                "downstream_consequence",
                "predictions_if_false",
                "falsification_requirements",
                "alternative_hypothesis_ids",
                "available_data",
                "remaining_cpu_hours",
            ],
        )

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
