from __future__ import annotations

from epistemic_loop.adapters.llm.base import StructuredLlm
from epistemic_loop.agents.experiment_designer import validate_preregistration
from epistemic_loop.agents.hypothesis_generator import validate_generated_hypotheses
from epistemic_loop.agents.proposal_bridge import (
    ExperimentBatch,
    FalsificationAssessment,
    HypothesisBatch,
    ProposalBridge,
)
from epistemic_loop.controller.run_state import RunState
from epistemic_loop.domain.models import (
    CompetitionWorldModel,
    ExperimentProposal,
    Hypothesis,
    Observation,
)


class AutomaticProposer:
    """Drives the three judgement calls in the loop through a structured-output LLM.

    `run_id` is normalized rather than trusted: it is bookkeeping the model has no business
    choosing. Everything the gates read — predictions, decision rules, costs, hypothesis links —
    is left exactly as proposed, so an unusable proposal is rejected instead of repaired.
    """

    def __init__(self, llm: StructuredLlm, bridge: ProposalBridge):
        self.llm = llm
        self.bridge = bridge

    def hypotheses(
        self,
        run_id: str,
        world_model: CompetitionWorldModel,
        state: RunState,
        *,
        maximum: int = 30,
    ) -> list[Hypothesis]:
        request = self.bridge.hypothesis_request(run_id, world_model, state)
        batch = self.llm.generate(request.prompt, HypothesisBatch, request.context)
        proposed = [item.model_copy(update={"run_id": run_id}) for item in batch.hypotheses]
        validate_generated_hypotheses(proposed, maximum=maximum)
        return proposed

    def experiments(self, run_id: str, state: RunState) -> list[ExperimentProposal]:
        request = self.bridge.experiment_request(run_id, state)
        batch = self.llm.generate(request.prompt, ExperimentBatch, request.context)
        proposed = [item.model_copy(update={"run_id": run_id}) for item in batch.experiments]
        for proposal in proposed:
            validate_preregistration(proposal)
        return proposed

    def assess(
        self,
        run_id: str,
        hypothesis: Hypothesis,
        observations: list[Observation],
        proposal: ExperimentProposal | None = None,
    ) -> FalsificationAssessment:
        request = self.bridge.falsification_request(run_id, hypothesis, observations, proposal)
        assessment = self.llm.generate(request.prompt, FalsificationAssessment, request.context)
        return assessment.model_copy(update={"hypothesis_id": hypothesis.id})
