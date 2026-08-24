from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from epistemic_loop.domain.enums import ExperimentStatus, ExperimentType, LoopState, Phase, RunStatus
from epistemic_loop.domain.events import EventEnvelope, EventType
from epistemic_loop.domain.models import (
    BeliefUpdate,
    BudgetUsage,
    CostEstimate,
    DecisionRecord,
    ExperimentProposal,
    FalsificationRecord,
    Hypothesis,
    Observation,
    ResearchBrief,
    ResearchRun,
)
from epistemic_loop.domain.validation import GateContext, experiment_fingerprint
from epistemic_loop.holdout.adaptivity import validation_reuse as compute_validation_reuse

SETTLED_STATUSES = frozenset(
    {
        ExperimentStatus.SELECTED,
        ExperimentStatus.RUNNING,
        ExperimentStatus.COMPLETED,
        ExperimentStatus.FAILED,
    }
)


def _accumulate(usage: BudgetUsage, estimate: CostEstimate) -> BudgetUsage:
    """Fold a reservation into usage without raising; budget refusal belongs to the gate."""
    return usage.model_copy(
        update={
            "experiments": usage.experiments + 1,
            "cpu_hours": usage.cpu_hours + estimate.cpu_hours,
            "gpu_hours": usage.gpu_hours + estimate.gpu_hours,
            "wall_hours": usage.wall_hours + estimate.wall_hours,
            "llm_tokens": usage.llm_tokens + estimate.llm_tokens,
            "cost": usage.cost + estimate.monetary_cost,
        }
    )


@dataclass(frozen=True)
class RunState:
    """Deterministic fold of the canonical event log; never a source of truth itself."""

    run: ResearchRun
    loop_state: LoopState
    phase: Phase
    hypotheses: dict[str, Hypothesis]
    proposals: dict[str, ExperimentProposal]
    experiment_statuses: dict[str, ExperimentStatus]
    observations: dict[str, Observation]
    falsifications: dict[str, FalsificationRecord]
    usage: BudgetUsage
    selection_order: tuple[str, ...]
    violations: int
    brief: ResearchBrief | None = None

    @property
    def run_id(self) -> str:
        return self.run.id

    def experiments_with_status(self, *statuses: ExperimentStatus) -> list[ExperimentProposal]:
        wanted = set(statuses)
        return [
            proposal
            for identifier, proposal in self.proposals.items()
            if self.experiment_statuses.get(identifier, ExperimentStatus.PROPOSED) in wanted
        ]

    def open_candidates(self) -> list[ExperimentProposal]:
        return self.experiments_with_status(ExperimentStatus.PROPOSED)

    def settled_experiment_ids(self) -> frozenset[str]:
        return frozenset(
            identifier for identifier in self.proposals if self.experiment_statuses.get(identifier) in SETTLED_STATUSES
        )

    def validation_reuse(self) -> dict[str, int]:
        """Selecting queries already spent against each validation scheme in this run."""
        return compute_validation_reuse(self.proposals, self.settled_experiment_ids())

    def falsification_digest(self) -> list[dict[str, object]]:
        """What the falsifier concluded, in the form the next round's proposals need to see.

        Alternative explanations and recommended next tests are the loop's memory of what has already
        been ruled out; without them the generator re-proposes hypotheses the evidence already
        weakened.
        """
        return [
            {
                "hypothesis_id": record.hypothesis_id,
                "disposition": record.disposition.value,
                "strongest_alternative_explanation": record.strongest_alternative_explanation,
                "confounders_checked": list(record.confounders_checked),
                "recommended_next_test": record.recommended_next_test,
                "alternative_claims": list(record.alternative_claims),
                "observation_ids": list(record.observation_ids),
            }
            for record in self.falsifications.values()
        ]

    def failed_experiments(self) -> list[dict[str, object]]:
        """Failures are evidence too: a design that cannot run must not be proposed again unchanged."""
        return [
            {
                "experiment_id": identifier,
                "experiment_type": proposal.experiment_type.value,
                "hypothesis_ids": list(proposal.hypothesis_ids),
                "research_question": proposal.research_question,
                "failure_class": next(
                    (
                        item.failure_class.value
                        for item in self.observations.values()
                        if item.experiment_id == identifier and item.failure_class is not None
                    ),
                    None,
                ),
            }
            for identifier, proposal in self.proposals.items()
            if self.experiment_statuses.get(identifier) == ExperimentStatus.FAILED
        ]

    def settled_fingerprints(self) -> frozenset[str]:
        """Only experiments that were actually committed to may block a duplicate."""
        return frozenset(
            experiment_fingerprint(proposal)
            for identifier, proposal in self.proposals.items()
            if self.experiment_statuses.get(identifier) in SETTLED_STATUSES
        )

    def recent_experiment_types(self, window: int = 3) -> tuple[ExperimentType, ...]:
        recent = [
            self.proposals[identifier].experiment_type
            for identifier in self.selection_order
            if identifier in self.proposals
        ]
        return tuple(recent[-window:])

    def observations_for(self, experiment_id: str) -> list[Observation]:
        return [item for item in self.observations.values() if item.experiment_id == experiment_id]

    def unjudged_observations(self) -> list[Observation]:
        """Observations no falsification record has interpreted yet; the resume point of a round."""
        judged = {identifier for record in self.falsifications.values() for identifier in record.observation_ids}
        return [item for item in self.observations.values() if item.id not in judged]

    def gate_context(
        self,
        *,
        source_policy_strict: bool = True,
        max_validation_reuse: int = 0,
        max_consecutive_optimization: int = 3,
    ) -> GateContext:
        return GateContext(
            hypothesis_ids=frozenset(self.hypotheses),
            budget=self.run.budgets,
            usage=self.usage,
            holdout_policy=self.run.holdout_policy.policy,
            prior_fingerprints=self.settled_fingerprints(),
            recent_experiment_types=self.recent_experiment_types(window=max(max_consecutive_optimization, 1)),
            source_policy_strict=source_policy_strict,
            validation_reuse=self.validation_reuse(),
            max_validation_reuse=max_validation_reuse,
            max_consecutive_optimization=max_consecutive_optimization,
        )


def load_run_state(events: Sequence[EventEnvelope]) -> RunState:
    run: ResearchRun | None = None
    loop_state = LoopState.CREATED
    phase = Phase.DISCOVERY
    hypotheses: dict[str, Hypothesis] = {}
    proposals: dict[str, ExperimentProposal] = {}
    statuses: dict[str, ExperimentStatus] = {}
    observations: dict[str, Observation] = {}
    falsifications: dict[str, FalsificationRecord] = {}
    usage = BudgetUsage()
    selection_order: list[str] = []
    violations = 0
    brief: ResearchBrief | None = None

    for event in events:
        payload = event.payload
        if event.event_type == EventType.RUN_CREATED:
            run = ResearchRun.model_validate(payload)
            phase = run.phase
            usage = run.budget_usage
        elif event.event_type == EventType.STATE_CHANGED:
            loop_state = LoopState(payload["state"])
            run_status = payload.get("run_status")
            if run is not None and run_status:
                run = run.model_copy(update={"status": RunStatus(run_status)})
        elif event.event_type == EventType.PHASE_CHANGED:
            phase = Phase(payload["phase"])
            if phase != Phase.EXPLOITATION:
                # Returning the run to research retires the hand-off: an exploiter that resumes
                # later must receive a brief rebuilt from what the anomaly taught the run.
                brief = None
        elif event.event_type in {EventType.HYPOTHESIS_PROPOSED, EventType.HYPOTHESIS_REVISED}:
            hypothesis = Hypothesis.model_validate(payload)
            hypotheses[hypothesis.id] = hypothesis
        elif event.event_type == EventType.BELIEF_UPDATED:
            update = BeliefUpdate.model_validate(payload)
            existing = hypotheses.get(update.hypothesis_id)
            if existing is not None:
                hypotheses[existing.id] = existing.model_copy(
                    update={
                        "current_confidence": update.posterior_confidence,
                        "version": existing.version + 1,
                    }
                )
        elif event.event_type == EventType.EXPERIMENT_PROPOSED:
            proposal = ExperimentProposal.model_validate(payload)
            proposals[proposal.id] = proposal
            statuses.setdefault(proposal.id, proposal.status)
        elif event.event_type == EventType.EXPERIMENT_SELECTED:
            decision = DecisionRecord.model_validate(payload)
            for identifier in decision.rejected_reasons:
                statuses[identifier] = ExperimentStatus.REJECTED
            for identifier in decision.selected_experiment_ids:
                statuses[identifier] = ExperimentStatus.SELECTED
                selection_order.append(identifier)
                candidate = proposals.get(identifier)
                if candidate is not None:
                    usage = _accumulate(usage, candidate.estimated_cost)
        elif event.event_type == EventType.EXPERIMENT_STARTED:
            statuses[str(payload["experiment_id"])] = ExperimentStatus.RUNNING
        elif event.event_type == EventType.EXPERIMENT_COMPLETED:
            statuses[str(payload["experiment_id"])] = ExperimentStatus.COMPLETED
        elif event.event_type == EventType.EXPERIMENT_FAILED:
            statuses[str(payload["experiment_id"])] = ExperimentStatus.FAILED
        elif event.event_type == EventType.OBSERVATION_RECORDED:
            observation = Observation.model_validate(payload)
            observations[observation.id] = observation
        elif event.event_type == EventType.FALSIFICATION_RECORDED:
            record = FalsificationRecord.model_validate(payload)
            falsifications[record.id] = record
        elif event.event_type == EventType.RESEARCH_BRIEF_CREATED:
            brief = ResearchBrief.model_validate(payload)
        elif event.event_type == EventType.VIOLATION_DETECTED:
            violations += 1
            if run is not None:
                run = run.model_copy(update={"status": RunStatus.BLOCKED})
        elif event.event_type == EventType.RUN_FINALIZED:
            phase = Phase.FINALIZED
            if run is not None:
                run = run.model_copy(update={"status": RunStatus.COMPLETED})

    if run is None:
        raise ValueError("event log does not contain a RunCreated event")

    return RunState(
        run=run,
        loop_state=loop_state,
        phase=phase,
        hypotheses=hypotheses,
        proposals=proposals,
        experiment_statuses=statuses,
        observations=observations,
        falsifications=falsifications,
        usage=usage,
        selection_order=tuple(selection_order),
        violations=violations,
        brief=brief,
    )
