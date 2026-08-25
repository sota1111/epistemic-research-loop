from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from epistemic_loop.domain.enums import ExperimentStatus, ExperimentType, HypothesisType, LoopState, Phase, RunStatus
from epistemic_loop.domain.events import EventEnvelope, EventType
from epistemic_loop.domain.models import (
    AgentResourceRecord,
    BeliefUpdate,
    BudgetUsage,
    CompetitionWorldModel,
    CostEstimate,
    DecisionRecord,
    ExperimentProposal,
    ExperimentRetryRecord,
    FalsificationProposal,
    FalsificationRecord,
    FinalSelectionRule,
    ForecastCalibrationRecord,
    Hypothesis,
    Observation,
    OOFArtifact,
    OOFEnsemble,
    QDCandidate,
    ResearchBrief,
    ResearchRun,
    ResourceReconciliation,
    ValidationWorld,
    ValidationWorldUpdate,
)
from epistemic_loop.domain.validation import GateContext, experiment_fingerprint
from epistemic_loop.holdout.adaptivity import validation_reuse as compute_validation_reuse
from epistemic_loop.qd.archive import QDArchive
from epistemic_loop.qd.descriptors import descriptor_names_for_mode

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


def _reconcile(usage: BudgetUsage, reconciliation: ResourceReconciliation) -> BudgetUsage:
    estimated = reconciliation.estimated
    charged = reconciliation.charged
    return usage.model_copy(
        update={
            "cpu_hours": max(0.0, usage.cpu_hours - estimated.cpu_hours + charged.cpu_hours),
            "gpu_hours": max(0.0, usage.gpu_hours - estimated.gpu_hours + charged.gpu_hours),
            "wall_hours": max(0.0, usage.wall_hours - estimated.wall_hours + charged.wall_hours),
            "llm_tokens": max(0, usage.llm_tokens - estimated.llm_tokens + charged.llm_tokens),
            "cost": max(0.0, usage.cost - estimated.monetary_cost + charged.monetary_cost),
        }
    )


def _accumulate_agent_usage(usage: BudgetUsage, record: AgentResourceRecord) -> BudgetUsage:
    return usage.model_copy(
        update={
            "llm_tokens": usage.llm_tokens + record.total_tokens,
            "cost": usage.cost + record.monetary_cost,
        }
    )


def _accumulate_retry_usage(usage: BudgetUsage, record: ExperimentRetryRecord) -> BudgetUsage:
    """Charge a worker attempt without counting it as another research experiment."""
    charged = record.charged_cost
    return usage.model_copy(
        update={
            "cpu_hours": usage.cpu_hours + charged.cpu_hours,
            "gpu_hours": usage.gpu_hours + charged.gpu_hours,
            "wall_hours": usage.wall_hours + charged.wall_hours,
            "llm_tokens": usage.llm_tokens + charged.llm_tokens,
            "cost": usage.cost + charged.monetary_cost,
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
    #: What the run knows about the competition, including the interface it must write commands
    #: against. A designer that cannot see this invents entry points that do not exist.
    world_model: CompetitionWorldModel | None = None
    #: Attempt number each experiment was last dispatched under. Needed to rebuild the worker
    #: request after a restart: the idempotency key contains the attempt, and for an executor that
    #: files a ticket the key *is* how a retry finds the ticket it already filed. Rebuilding at
    #: attempt 1 when attempt 2 is outstanding opens a second ticket for the same work.
    experiment_attempts: dict[str, int] = field(default_factory=dict)
    validation_worlds: dict[str, ValidationWorld] = field(default_factory=dict)
    qd_candidates: dict[str, QDCandidate] = field(default_factory=dict)
    oof_artifacts: dict[str, OOFArtifact] = field(default_factory=dict)
    falsification_proposals: dict[str, FalsificationProposal] = field(default_factory=dict)
    oof_analyses: tuple[dict[str, Any], ...] = ()
    oof_ensembles: dict[str, OOFEnsemble] = field(default_factory=dict)
    final_selection_rule: FinalSelectionRule | None = None
    forecast_calibrations: tuple[ForecastCalibrationRecord, ...] = ()
    agent_resource_records: tuple[AgentResourceRecord, ...] = ()
    experiment_retries: tuple[ExperimentRetryRecord, ...] = ()

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

    def observed_runtime(self) -> dict[str, float]:
        """What the experiments actually cost, as opposed to what they were estimated to cost.

        Budget gates spend the *estimate* a proposal declared, and nothing has ever compared that
        against the observation that came back. A run whose estimates are optimistic can therefore
        consume several times its nominal compute without any gate noticing, which also silently
        breaks the equal-budget premise of any A/B comparison built on those runs.
        """
        wall_hours = sum(
            observation.resource_usage.wall_hours
            if observation.resource_usage.wall_hours is not None
            else float(observation.runtime.get("wall_seconds", 0.0)) / 3600
            for observation in self.observations.values()
        ) + sum(item.charged_cost.wall_hours for item in self.experiment_retries)
        cpu_hours = sum(
            observation.resource_usage.cpu_hours or 0.0 for observation in self.observations.values()
        ) + sum(item.charged_cost.cpu_hours for item in self.experiment_retries)
        gpu_hours = sum(
            observation.resource_usage.gpu_hours or 0.0 for observation in self.observations.values()
        ) + sum(item.charged_cost.gpu_hours for item in self.experiment_retries)
        estimated_wall_hours = sum(
            self.proposals[identifier].estimated_cost.wall_hours
            for identifier in dict.fromkeys(self.selection_order)
            if identifier in self.proposals
        )
        return {
            "cpu_hours": round(cpu_hours, 4),
            "gpu_hours": round(gpu_hours, 4),
            "wall_hours": round(wall_hours, 4),
            "estimated_wall_hours": round(estimated_wall_hours, 4),
            "charged_wall_hours": round(self.usage.wall_hours, 4),
            "estimate_ratio": round(wall_hours / estimated_wall_hours, 2) if estimated_wall_hours else 0.0,
            "experiments_observed": len(self.observations),
            "retry_attempts": len(self.experiment_retries),
        }

    def validation_reuse(self) -> dict[str, int]:
        """Selecting queries already spent against each validation scheme in this run."""
        return compute_validation_reuse(self.proposals, self.settled_experiment_ids())

    def observation_digest(self, limit: int = 12) -> list[dict[str, object]]:
        """What the experiments actually measured, in the form the next proposal needs to see.

        Falsification records carry the run's *interpretations* forward, which is not the same as
        its measurements: a number nobody thought to write into a verdict is invisible to the next
        round even though the loop holds it. That makes the loop's memory a function of how
        diligently each verdict was written rather than of what was observed, and a proposer that
        cannot see the numbers cannot notice what the verdicts missed.
        """
        recent = sorted(self.observations.values(), key=lambda item: item.created_at)[-limit:]
        return [
            {
                "experiment_id": item.experiment_id,
                "metrics": item.metrics,
                "fold_metrics": item.fold_metrics,
                "subgroup_metrics": item.subgroup_metrics,
                "exit_status": item.exit_status,
                "failure_class": item.failure_class.value if item.failure_class else None,
            }
            for item in recent
        ]

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
                "command": proposal.implementation_request.get("command"),
                "failure_excerpt": next(
                    (
                        item.failure_excerpt
                        for item in self.observations.values()
                        if item.experiment_id == identifier and item.failure_excerpt
                    ),
                    None,
                ),
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

    def retained_qd_candidates(
        self,
        *,
        maximum_size: int = 100,
        quality_floor_relative_to_best: float = 0.97,
    ) -> tuple[QDCandidate, ...]:
        names = descriptor_names_for_mode(self.run.mode)
        if not names or not self.qd_candidates:
            return ()
        return QDArchive.rebuild(
            self.qd_candidates.values(),
            descriptor_names=names,
            maximum_size=maximum_size,
            quality_floor_relative_to_best=quality_floor_relative_to_best,
        ).candidates

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
        enforce_brief: bool = True,
        command_allowlist: tuple[str, ...] = (),
        required_request_fields: tuple[str, ...] = (),
        required_brief_fields: tuple[str, ...] = (),
        qd_maximum_size: int = 100,
        qd_quality_floor_relative_to_best: float = 0.97,
    ) -> GateContext:
        retained_candidates = self.retained_qd_candidates(
            maximum_size=qd_maximum_size,
            quality_floor_relative_to_best=qd_quality_floor_relative_to_best,
        )
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
            command_allowlist=command_allowlist,
            required_request_fields=required_request_fields,
            required_brief_fields=required_brief_fields,
            # Only once a brief exists and the run is exploiting: during research there is no
            # approved set yet, and constraining discovery to one would defeat the point.
            approved_lineages=(
                frozenset(self.brief.approved_model_lineages)
                if enforce_brief and self.brief and self.phase == Phase.EXPLOITATION
                else frozenset()
            ),
            prohibited_shortcuts=(
                tuple(self.brief.prohibited_shortcuts)
                if enforce_brief and self.brief and self.phase == Phase.EXPLOITATION
                else ()
            ),
            run_mode=self.run.mode,
            hypotheses_with_alternatives=frozenset(
                identifier for identifier, item in self.hypotheses.items() if item.alternative_hypothesis_ids
            ),
            validation_hypothesis_ids=frozenset(
                identifier for identifier, item in self.hypotheses.items() if item.type == HypothesisType.VALIDATION
            ),
            validation_world_ids=frozenset(self.validation_worlds),
            qd_candidate_ids=frozenset(item.id for item in retained_candidates),
            falsification_targets={
                identifier: item.target_hypothesis for identifier, item in self.falsification_proposals.items()
            },
        )


def load_run_state(events: Sequence[EventEnvelope]) -> RunState:
    run: ResearchRun | None = None
    loop_state = LoopState.CREATED
    phase = Phase.DISCOVERY
    hypotheses: dict[str, Hypothesis] = {}
    proposals: dict[str, ExperimentProposal] = {}
    statuses: dict[str, ExperimentStatus] = {}
    attempts: dict[str, int] = {}
    observations: dict[str, Observation] = {}
    falsifications: dict[str, FalsificationRecord] = {}
    falsification_proposals: dict[str, FalsificationProposal] = {}
    validation_worlds: dict[str, ValidationWorld] = {}
    qd_candidates: dict[str, QDCandidate] = {}
    oof_artifacts: dict[str, OOFArtifact] = {}
    oof_analyses: list[dict[str, Any]] = []
    oof_ensembles: dict[str, OOFEnsemble] = {}
    final_selection_rule: FinalSelectionRule | None = None
    forecast_calibrations: list[ForecastCalibrationRecord] = []
    agent_resource_records: list[AgentResourceRecord] = []
    experiment_retries: list[ExperimentRetryRecord] = []
    usage = BudgetUsage()
    selection_order: list[str] = []
    violations = 0
    brief: ResearchBrief | None = None
    world_model: CompetitionWorldModel | None = None

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
        elif event.event_type == EventType.FORECAST_CALIBRATION_RECORDED:
            forecast_calibrations.append(ForecastCalibrationRecord.model_validate(payload))
        elif event.event_type == EventType.AGENT_RESOURCE_RECORDED:
            agent_record = AgentResourceRecord.model_validate(payload)
            agent_resource_records.append(agent_record)
            usage = _accumulate_agent_usage(usage, agent_record)
        elif event.event_type == EventType.EXPERIMENT_RETRY_SCHEDULED:
            retry_record = ExperimentRetryRecord.model_validate(payload)
            experiment_retries.append(retry_record)
            usage = _accumulate_retry_usage(usage, retry_record)
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
            attempts[str(payload["experiment_id"])] = int(payload.get("attempt", 1))
        elif event.event_type == EventType.EXPERIMENT_COMPLETED:
            statuses[str(payload["experiment_id"])] = ExperimentStatus.COMPLETED
        elif event.event_type == EventType.EXPERIMENT_FAILED:
            statuses[str(payload["experiment_id"])] = ExperimentStatus.FAILED
        elif event.event_type == EventType.RESOURCE_RECONCILED:
            usage = _reconcile(usage, ResourceReconciliation.model_validate(payload))
        elif event.event_type == EventType.OBSERVATION_RECORDED:
            observation = Observation.model_validate(payload)
            observations[observation.id] = observation
        elif event.event_type == EventType.FALSIFICATION_RECORDED:
            record = FalsificationRecord.model_validate(payload)
            falsifications[record.id] = record
        elif event.event_type == EventType.FALSIFICATION_PROPOSED:
            falsification_proposal = FalsificationProposal.model_validate(payload)
            falsification_proposals[falsification_proposal.id] = falsification_proposal
        elif event.event_type == EventType.VALIDATION_WORLD_REGISTERED:
            validation_world = ValidationWorld.model_validate(payload)
            validation_worlds[validation_world.id] = validation_world
        elif event.event_type == EventType.VALIDATION_POSTERIOR_UPDATED:
            world_update = ValidationWorldUpdate.model_validate(payload)
            for identifier, probability in world_update.posterior.items():
                current_world = validation_worlds.get(identifier)
                if current_world is not None:
                    validation_worlds[identifier] = current_world.model_copy(
                        update={
                            "posterior_probability": probability,
                            "evidence_ids": [*current_world.evidence_ids, world_update.evidence_id],
                            "version": current_world.version + 1,
                        }
                    )
        elif event.event_type == EventType.QD_CANDIDATE_EVALUATED:
            qd_candidate = QDCandidate.model_validate(payload)
            qd_candidates[qd_candidate.id] = qd_candidate
        elif event.event_type == EventType.OOF_ARTIFACT_RECORDED:
            artifact = OOFArtifact.model_validate(payload)
            oof_artifacts[artifact.id] = artifact
        elif event.event_type == EventType.OOF_ANALYSIS_RECORDED:
            oof_analyses.append(dict(payload))
        elif event.event_type == EventType.OOF_ENSEMBLE_CREATED:
            ensemble = OOFEnsemble.model_validate(payload)
            oof_ensembles[ensemble.id] = ensemble
        elif event.event_type == EventType.WORLD_MODEL_RECORDED:
            world_model = CompetitionWorldModel.model_validate(payload)
        elif event.event_type == EventType.RESEARCH_BRIEF_CREATED:
            brief = ResearchBrief.model_validate(payload)
        elif event.event_type == EventType.FINAL_SELECTION_RULE_REGISTERED:
            final_selection_rule = FinalSelectionRule.model_validate(payload)
        elif event.event_type == EventType.VIOLATION_DETECTED:
            violations += 1
            if run is not None:
                run = run.model_copy(update={"status": RunStatus.BLOCKED})
        elif event.event_type == EventType.RUN_FINALIZED:
            phase = Phase.FINALIZED
            if run is not None:
                run = run.model_copy(update={"status": RunStatus.COMPLETED, "finalized_at": event.occurred_at})

    if run is None:
        raise ValueError("event log does not contain a RunCreated event")

    return RunState(
        run=run,
        loop_state=loop_state,
        phase=phase,
        hypotheses=hypotheses,
        proposals=proposals,
        experiment_statuses=statuses,
        experiment_attempts=attempts,
        observations=observations,
        falsifications=falsifications,
        usage=usage,
        selection_order=tuple(selection_order),
        violations=violations,
        brief=brief,
        world_model=world_model,
        validation_worlds=validation_worlds,
        qd_candidates=qd_candidates,
        oof_artifacts=oof_artifacts,
        falsification_proposals=falsification_proposals,
        oof_analyses=tuple(oof_analyses),
        oof_ensembles=oof_ensembles,
        final_selection_rule=final_selection_rule,
        forecast_calibrations=tuple(forecast_calibrations),
        agent_resource_records=tuple(agent_resource_records),
        experiment_retries=tuple(experiment_retries),
    )
