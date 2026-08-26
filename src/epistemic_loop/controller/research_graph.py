from __future__ import annotations

import csv
import hashlib
import json
import mimetypes
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from epistemic_loop.adapters.executor.base import ExecutionContract, ExecutorAdapter
from epistemic_loop.agents.experiment_designer import validate_preregistration
from epistemic_loop.agents.falsifier import Falsifier
from epistemic_loop.agents.hypothesis_generator import validate_generated_hypotheses
from epistemic_loop.belief.calibration import summarize_calibration
from epistemic_loop.config import AppConfig, PhaseWeights, config_hash
from epistemic_loop.contamination.anonymize import anonymous_identifier
from epistemic_loop.controller.allocation import adaptive_allocation
from epistemic_loop.controller.budget_manager import BudgetManager
from epistemic_loop.controller.execution_contract import build_experiment_request
from epistemic_loop.controller.mode_policy import capabilities
from epistemic_loop.controller.phase_policy import PhaseEvidence, decide_phase
from epistemic_loop.controller.research_state import derive_research_state
from epistemic_loop.controller.run_state import RunState, load_run_state
from epistemic_loop.controller.state_machine import ResearchStateMachine
from epistemic_loop.domain.enums import (
    ExperimentStatus,
    ExperimentType,
    FailureClass,
    HypothesisStatus,
    LoopState,
    Phase,
    RunStatus,
)
from epistemic_loop.domain.events import EventType
from epistemic_loop.domain.models import (
    AgentResourceRecord,
    ArtifactRef,
    BeliefUpdate,
    CompetitionWorldModel,
    CostEstimate,
    DecisionRecord,
    ExperimentManifest,
    ExperimentProposal,
    ExperimentRequest,
    ExperimentResult,
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
    ValidationWorldEvidence,
)
from epistemic_loop.holdout.violations import HoldoutViolation
from epistemic_loop.qd.archive import ArchiveUpdate, QDArchive
from epistemic_loop.qd.descriptors import descriptor_names_for_mode
from epistemic_loop.qd.finalizer import select_final_candidate
from epistemic_loop.scoring.cost import normalized_cost
from epistemic_loop.scoring.robustness import robustness_value
from epistemic_loop.scoring.selector import ScoredCandidate, evaluate_candidates, select_portfolio
from epistemic_loop.storage.repositories import ResearchRepository
from epistemic_loop.validation.worlds import expected_score, update_worlds, validate_world_distribution

POLICY_VERSION = "selection/v2"
SIDECAR_METRICS = {
    "fold_metrics": "fold_metrics.json",
    "seed_metrics": "seed_metrics.json",
    "subgroup_metrics": "subgroup_metrics.json",
}


class LoopStateError(RuntimeError):
    """Raised when a loop step is attempted from a state that does not permit it."""


class ResearchController:
    """Small application service; policies stay deterministic and event-sourced."""

    def __init__(self, repository: ResearchRepository):
        self.repository = repository

    # ------------------------------------------------------------------ state

    def state(self, run_id: str) -> RunState:
        return load_run_state(self.repository.event_store(run_id).read_all())

    def _advance(self, run_id: str, current: LoopState, target: LoopState, allowed: set[LoopState]) -> None:
        if current == target:
            return
        if current not in allowed:
            raise LoopStateError(f"cannot move from {current.value} to {target.value}")
        machine = ResearchStateMachine(current)
        machine.transition(target)
        self.repository.append(
            run_id,
            EventType.STATE_CHANGED,
            {"state": target.value, "run_status": RunStatus.RUNNING.value},
        )

    # ------------------------------------------------------------- lifecycle

    def create_run(
        self,
        config: AppConfig,
        *,
        base_commit_sha: str,
        dataset_fingerprint: str,
        run_id: str | None = None,
    ) -> ResearchRun:
        hashed_config = config_hash(config)
        competition_id = (
            anonymous_identifier(config.competition.slug, salt=hashed_config)
            if config.contamination.obfuscate_competition_name
            else config.competition.slug
        )
        identifier = run_id or config.run.id or f"{competition_id}-{uuid.uuid4().hex[:8]}"
        run = ResearchRun(
            id=identifier,
            competition_id=competition_id,
            primary_metric=config.competition.primary_metric,
            metric_direction=config.competition.metric_direction,
            sample_submission=config.competition.sample_submission,
            max_public_queries=config.leaderboard.max_public_queries,
            mode=config.run.mode,
            phase=Phase.DISCOVERY,
            seed=config.run.seed,
            status=RunStatus.CREATED,
            base_commit_sha=base_commit_sha,
            dataset_fingerprint=dataset_fingerprint,
            config_hash=hashed_config,
            budgets=config.budgets,
            holdout_policy=config.holdout,
        )
        self.repository.append(identifier, EventType.RUN_CREATED, run)
        self.repository.append(
            identifier,
            EventType.STATE_CHANGED,
            {"state": LoopState.CREATED.value, "run_status": RunStatus.CREATED.value},
        )
        return run

    def start(self, run_id: str, world_model: CompetitionWorldModel) -> None:
        self.repository.append(
            run_id,
            EventType.STATE_CHANGED,
            {"state": LoopState.OBSERVING.value, "run_status": RunStatus.RUNNING.value},
        )
        self.repository.append(run_id, EventType.WORLD_MODEL_RECORDED, world_model)
        self.repository.append(
            run_id,
            EventType.STATE_CHANGED,
            {"state": LoopState.HYPOTHESIZING.value, "run_status": RunStatus.RUNNING.value},
        )

    # ------------------------------------------------------------- loop steps

    def record_hypotheses(
        self,
        run_id: str,
        hypotheses: Sequence[Hypothesis],
        *,
        max_active: int = 30,
        calibration_minimum_records: int = 3,
        poor_brier_threshold: float = 0.25,
        prior_shrinkage: float = 0.25,
    ) -> list[str]:
        state = self.state(run_id)
        incoming = [
            _shrink_uncalibrated_prior(
                item,
                state,
                minimum_records=calibration_minimum_records,
                poor_brier_threshold=poor_brier_threshold,
                prior_shrinkage=prior_shrinkage,
            )
            for item in hypotheses
        ]
        for hypothesis in incoming:
            if hypothesis.run_id != run_id:
                raise ValueError(f"hypothesis {hypothesis.id} belongs to run {hypothesis.run_id}")
            known = state.hypotheses.get(hypothesis.id)
            if known is not None:
                predictions_changed = (
                    hypothesis.predictions_if_true != known.predictions_if_true
                    or hypothesis.predictions_if_false != known.predictions_if_false
                )
                committed = any(
                    hypothesis.id in proposal.hypothesis_ids
                    and state.experiment_statuses.get(identifier)
                    in {
                        ExperimentStatus.SELECTED,
                        ExperimentStatus.RUNNING,
                        ExperimentStatus.COMPLETED,
                        ExperimentStatus.FAILED,
                    }
                    for identifier, proposal in state.proposals.items()
                )
                if predictions_changed and committed:
                    raise ValueError(f"hypothesis {hypothesis.id} predictions are frozen after experiment selection")
        active = [item for item in state.hypotheses.values() if item.status != HypothesisStatus.RETIRED]
        validate_generated_hypotheses(incoming, maximum=max_active)
        if len(active) + len(incoming) > max_active:
            raise ValueError(f"run would hold {len(active) + len(incoming)} active hypotheses; maximum is {max_active}")
        for hypothesis in incoming:
            known = state.hypotheses.get(hypothesis.id)
            event_type = EventType.HYPOTHESIS_REVISED if known else EventType.HYPOTHESIS_PROPOSED
            self.repository.append(run_id, event_type, hypothesis)
        self._advance(run_id, state.loop_state, LoopState.PLANNING, {LoopState.HYPOTHESIZING})
        return [item.id for item in incoming]

    def record_agent_resource(self, run_id: str, record: AgentResourceRecord) -> None:
        if record.run_id != run_id:
            raise ValueError("agent resource record belongs to another run")
        self.repository.append(run_id, EventType.AGENT_RESOURCE_RECORDED, record)

    def schedule_infrastructure_retry(
        self,
        run_id: str,
        result: ExperimentResult,
    ) -> ExperimentRetryRecord:
        """Record and charge a failed attempt before permitting the next one."""
        state = self.state(run_id)
        proposal = _require_experiment(state, result.experiment_id)
        if result.run_id != run_id:
            raise ValueError("experiment result belongs to another run")
        failure_class = result.failure_class
        if result.status != "failed" or failure_class != FailureClass.INFRASTRUCTURE:
            raise ValueError("only terminal infrastructure failures may be retried automatically")
        current_attempt = state.experiment_attempts.get(result.experiment_id)
        if current_attempt != result.attempt:
            raise ValueError(f"result attempt {result.attempt} does not match running attempt {current_attempt}")
        reconciliation = _resource_reconciliation(state, proposal, result)
        charged = reconciliation.charged
        projected = state.usage.model_copy(
            update={
                "cpu_hours": state.usage.cpu_hours + charged.cpu_hours,
                "gpu_hours": state.usage.gpu_hours + charged.gpu_hours,
                "wall_hours": state.usage.wall_hours + charged.wall_hours,
                "llm_tokens": state.usage.llm_tokens + charged.llm_tokens,
                "cost": state.usage.cost + charged.monetary_cost,
            }
        )
        budget = state.run.budgets
        exceeded = [
            name
            for name, value, maximum in (
                ("max_cpu_hours", projected.cpu_hours, budget.max_cpu_hours),
                ("max_gpu_hours", projected.gpu_hours, budget.max_gpu_hours),
                ("max_wall_hours", projected.wall_hours, budget.max_wall_hours),
                ("max_llm_tokens", projected.llm_tokens, budget.max_llm_tokens),
            )
            if value > maximum
        ]
        if budget.max_cost and projected.cost > budget.max_cost:
            exceeded.append("max_cost")
        if exceeded:
            raise ValueError(f"retry would exceed budget: {', '.join(exceeded)}")
        record = ExperimentRetryRecord(
            id=f"ERR-{uuid.uuid4().hex[:12]}",
            run_id=run_id,
            experiment_id=result.experiment_id,
            failed_attempt=result.attempt,
            next_attempt=result.attempt + 1,
            failure_class=failure_class,
            failure_excerpt=result.failure_excerpt,
            resource_usage=result.resource_usage,
            charged_cost=charged,
        )
        self.repository.append(run_id, EventType.EXPERIMENT_RETRY_SCHEDULED, record)
        return record

    def record_proposals(self, run_id: str, proposals: Sequence[ExperimentProposal]) -> list[str]:
        state = self.state(run_id)
        # A reused identifier is a naming accident, not a research error. Failing the batch loses the
        # designs that were fine alongside it and ends the round, which is how the eighth unattended
        # run stopped at round two. Drop the collision, keep the rest, and fail only if nothing is
        # left -- there is no safe way to record two different designs under one identifier.
        recorded: list[ExperimentProposal] = []
        collisions: list[str] = []
        for proposal in proposals:
            if proposal.run_id != run_id:
                raise ValueError(f"experiment {proposal.id} belongs to run {proposal.run_id}")
            if proposal.id in state.proposals or any(proposal.id == item.id for item in recorded):
                collisions.append(proposal.id)
                continue
            validate_preregistration(proposal)
            recorded.append(proposal)
        if not recorded:
            raise ValueError(f"every proposed experiment reuses an existing identifier: {collisions}")
        for proposal in recorded:
            self.repository.append(run_id, EventType.EXPERIMENT_PROPOSED, proposal)
        self._advance(run_id, state.loop_state, LoopState.SCORING, {LoopState.PLANNING})
        return [item.id for item in recorded]

    def select_experiments(
        self,
        run_id: str,
        *,
        weights: PhaseWeights,
        cost_lambda: float = 0.15,
        risk_lambda: float = 0.5,
        size: int = 1,
        minimum_utility: float = float("-inf"),
        similarity_penalty: float = 0.25,
        allocation: dict[str, float] | None = None,
        source_policy_strict: bool = True,
        max_validation_reuse: int = 0,
        max_consecutive_optimization: int = 3,
        max_consecutive_diagnostics: int = 3,
        require_candidate_after_diagnostics: bool = False,
        enforce_v2_contract: bool = False,
        command_allowlist: tuple[str, ...] = (),
        execution_contract: ExecutionContract | None = None,
        eig_method: Literal["exact", "monte_carlo"] = "exact",
        eig_monte_carlo_samples: int = 4000,
        preferred_state_targets: Mapping[str, float] | None = None,
        preferred_state_weights: Mapping[str, float] | None = None,
        qd_maximum_size: int = 100,
        qd_quality_floor_relative_to_best: float = 0.97,
        information_value_enabled: bool = True,
        preferred_state_enabled: bool = True,
    ) -> DecisionRecord:
        state = self.state(run_id)
        candidates = state.open_candidates()
        if not candidates:
            raise ValueError("no proposed experiments are available for selection")
        if state.loop_state == LoopState.PLANNING:
            # A round with nothing new to propose is legitimate: a preregistered candidate set is
            # meant to be worked through one experiment at a time, and forcing a fresh proposal each
            # round just to reach `scoring` would make the run invent work it does not want. Entering
            # `scoring` from `planning` is only allowed while candidates are actually standing.
            self._advance(run_id, LoopState.PLANNING, LoopState.SCORING, {LoopState.PLANNING})
            state = self.state(run_id)
        scored = evaluate_candidates(
            candidates,
            state.gate_context(
                source_policy_strict=source_policy_strict,
                max_validation_reuse=max_validation_reuse,
                max_consecutive_optimization=max_consecutive_optimization,
                max_consecutive_diagnostics=max_consecutive_diagnostics,
                require_candidate_after_diagnostics=require_candidate_after_diagnostics,
                enforce_v2_contract=enforce_v2_contract,
                command_allowlist=command_allowlist,
                required_request_fields=execution_contract.required_fields if execution_contract else (),
                required_brief_fields=execution_contract.required_brief_fields if execution_contract else (),
                qd_maximum_size=qd_maximum_size,
                qd_quality_floor_relative_to_best=qd_quality_floor_relative_to_best,
            ),
            weights,
            cost_lambda,
            beliefs={identifier: item.current_confidence for identifier, item in state.hypotheses.items()},
            mode=state.run.mode,
            risk_lambda=risk_lambda,
            eig_method=eig_method,
            eig_monte_carlo_samples=eig_monte_carlo_samples,
            random_seed=state.run.seed,
            information_value_enabled=information_value_enabled,
        )
        research_state = derive_research_state(
            state,
            maximum_archive_size=qd_maximum_size,
            preferred_targets=preferred_state_targets,
            preferred_weights=preferred_state_weights,
        )
        selected = select_portfolio(
            scored,
            size,
            similarity_penalty=similarity_penalty,
            minimum_utility=minimum_utility,
            allocation=(
                adaptive_allocation(
                    allocation,
                    mode=state.run.mode,
                    validation_worlds=list(state.validation_worlds.values()),
                    qd_occupancy=len(
                        state.retained_qd_candidates(
                            maximum_size=qd_maximum_size,
                            quality_floor_relative_to_best=qd_quality_floor_relative_to_best,
                        )
                    ),
                    preferred_state_gap=(research_state.preferred_state_total_gap if preferred_state_enabled else None),
                )
                if allocation
                else None
            ),
        )
        decision = DecisionRecord(
            id=f"DR-{uuid.uuid4().hex[:12]}",
            run_id=run_id,
            candidate_experiment_ids=[item.proposal.id for item in scored],
            utility_breakdown={item.proposal.id: (item.utility.__dict__ if item.utility else None) for item in scored},
            selected_experiment_ids=[item.proposal.id for item in selected],
            rejected_reasons=_rejected_reasons(scored, selected, minimum_utility),
            phase=state.phase,
            remaining_budget=BudgetManager(state.run.budgets, state.usage).remaining(),
            policy_version=POLICY_VERSION,
        )
        self.repository.append(run_id, EventType.EXPERIMENT_SELECTED, decision)
        self._advance(run_id, state.loop_state, LoopState.SELECTING, {LoopState.SCORING})
        return decision

    def dispatch(
        self,
        run_id: str,
        experiment_id: str,
        executor: ExecutorAdapter,
        *,
        container_image: str,
        dataset_mounts: Sequence[str] = (),
        network_policy: str = "disabled",
        attempt: int = 1,
    ) -> tuple[ExperimentRequest, ExperimentResult]:
        state = self.state(run_id)
        proposal = _require_experiment(state, experiment_id)
        status = state.experiment_statuses.get(experiment_id)
        # The attempt is recorded before the side effect, so a failed hand-off leaves the experiment
        # running; a retry must therefore be allowed, but only under an explicit new attempt number.
        retryable = status == ExperimentStatus.RUNNING and attempt > 1
        if status != ExperimentStatus.SELECTED and not retryable:
            raise LoopStateError(f"experiment {experiment_id} is {status} and may not be dispatched")
        if retryable and attempt != state.experiment_attempts.get(experiment_id, 1) + 1:
            raise LoopStateError("retry attempts must be consecutive")
        if state.loop_state == LoopState.PLANNING and status == ExperimentStatus.SELECTED:
            # A selection is a commitment the run already recorded, with its preregistration
            # already in the log. A round that advanced past it without dispatching leaves it
            # stranded, and refusing to honour it because the loop has since reached `planning`
            # discards a decision rather than protecting one. Re-entering `selecting` is safe
            # precisely because the selection event -- and everything it fixed -- already exists.
            self._advance(run_id, LoopState.PLANNING, LoopState.SCORING, {LoopState.PLANNING})
            self._advance(run_id, LoopState.SCORING, LoopState.SELECTING, {LoopState.SCORING})
            state = self.state(run_id)
        request = build_experiment_request(
            state.run,
            proposal,
            attempt=attempt,
            container_image=container_image,
            dataset_mounts=dataset_mounts,
            network_policy=network_policy,
            contract=executor.contract,
        )
        # Enter `executing` before recording the attempt. Recording first would mark the experiment
        # running even when the transition is refused, burning it: the status check above then only
        # allows a retry under a new attempt number, so a call that never reached the executor would
        # cost a real attempt every time it was repeated.
        self._advance(run_id, state.loop_state, LoopState.EXECUTING, {LoopState.SELECTING})
        self.repository.append(
            run_id,
            EventType.EXPERIMENT_STARTED,
            {
                "experiment_id": experiment_id,
                "request_id": request.request_id,
                "idempotency_key": request.idempotency_key,
                "attempt": attempt,
            },
        )
        return request, executor.submit(request)

    def import_result(
        self,
        run_id: str,
        result: ExperimentResult,
        *,
        artifact_root: str | Path | None = None,
        qd_maximum_size: int = 100,
        qd_quality_floor_relative_to_best: float = 0.97,
    ) -> Observation | None:
        state = self.state(run_id)
        _require_experiment(state, result.experiment_id)
        if result.status in {"queued", "running"}:
            return None
        if state.experiment_statuses.get(result.experiment_id) != ExperimentStatus.RUNNING:
            raise LoopStateError(
                f"experiment {result.experiment_id} was never dispatched; there is no result to import"
            )
        completed = result.status == "completed"
        proposal = state.proposals[result.experiment_id]
        observation = _observation_from_result(result, artifact_root, run=state.run, proposal=proposal)
        validation_evidence: ValidationWorldEvidence | None = None
        forecast = proposal.validation_world_forecast
        observed_label = result.observed_outcomes.get("validation_world")
        if completed and forecast is not None and observed_label:
            outcome = next((item for item in forecast.outcomes if item.label == observed_label), None)
            if outcome is None:
                raise ValueError(
                    f"observed validation outcome {observed_label!r} was not preregistered for {proposal.id}"
                )
            if set(outcome.probability_by_world) != set(state.validation_worlds):
                raise ValueError("validation outcome likelihoods do not match the run's active validation worlds")
            validation_evidence = ValidationWorldEvidence(
                id=f"VWE-{uuid.uuid4().hex[:12]}",
                run_id=run_id,
                observation_id=observation.id,
                likelihood_by_world=outcome.probability_by_world,
                reliability=result.metrics.get("validation_evidence_reliability", 1.0),
                metric_name=forecast.metric_name,
                observed_value=result.metrics.get(forecast.metric_name, 0.0),
                preregistration_ref=f"{proposal.id}/validation_world_forecast/{observed_label}",
            )
        self.repository.append(
            run_id,
            EventType.EXPERIMENT_COMPLETED if completed else EventType.EXPERIMENT_FAILED,
            result,
        )
        self.repository.append(run_id, EventType.OBSERVATION_RECORDED, observation)
        for calibration in _forecast_calibrations(state, proposal, result):
            self.repository.append(run_id, EventType.FORECAST_CALIBRATION_RECORDED, calibration)
        reconciliation = _resource_reconciliation(state, proposal, result)
        self.repository.append(run_id, EventType.RESOURCE_RECONCILED, reconciliation)
        if completed and proposal.descriptors is not None and capabilities(state.run.mode).solution_qd:
            metric = _posterior_weighted_metric(state, observation)
            if metric is not None:
                direction_adjusted = metric if state.run.metric_direction == "maximize" else -metric
                candidate = QDCandidate(
                    id=f"QD-{result.experiment_id}",
                    run_id=run_id,
                    experiment_id=result.experiment_id,
                    descriptors=proposal.descriptors,
                    expected_hidden_score=direction_adjusted,
                    score_variance=max(
                        proposal.expected_score_gain.fold_std,
                        proposal.expected_score_gain.seed_std,
                    ),
                    normalized_cost=normalized_cost(proposal.estimated_cost),
                    leakage_risk=0.5 if proposal.contamination_risk.value == "medium" else 0.0,
                    robustness=robustness_value(proposal.robustness_assessment),
                    artifact_ids=[item.sha256 for item in observation.artifacts],
                    oof_artifact=next(
                        (item.uri for item in observation.artifacts if "oof" in Path(item.uri).name.lower()),
                        None,
                    ),
                    reproduction_passed=result.metrics.get("reproduction_passed", 0.0) >= 1.0,
                    leakage_check_passed=result.metrics.get("leakage_check_passed", 0.0) >= 1.0,
                    fold_assignment_artifact=next(
                        (
                            item.uri
                            for item in observation.artifacts
                            if "fold_assignment" in Path(item.uri).name.lower()
                        ),
                        None,
                    ),
                    submission_procedure=(proposal.implementation_request.get("command") or proposal.protocol),
                )
                self.archive_candidate(
                    run_id,
                    candidate,
                    maximum_size=qd_maximum_size,
                    quality_floor_relative_to_best=qd_quality_floor_relative_to_best,
                )
        if validation_evidence is not None:
            self.update_validation_posterior(run_id, validation_evidence)
        if state.loop_state == LoopState.EXECUTING:
            self._advance(run_id, state.loop_state, LoopState.PARSING, {LoopState.EXECUTING})
        # Otherwise the result arrived late: the round timed out and moved on, so the loop is no
        # longer in `executing`. Forcing it back into `parsing` would corrupt whatever round it is
        # in now, but discarding the observation would lose evidence the run paid for -- and with an
        # asynchronous worker fleet, "slower than the caller's timeout" is ordinary, not exceptional.
        # The observation is recorded unjudged, so the next round's falsification step picks it up.
        return observation

    def record_falsification(self, run_id: str, record: FalsificationRecord) -> FalsificationRecord:
        state = self.state(run_id)
        if not capabilities(state.run.mode).independent_falsifier:
            raise ValueError(f"independent falsification is disabled in {state.run.mode.value}")
        if record.hypothesis_id not in state.hypotheses:
            raise ValueError(f"unknown hypothesis: {record.hypothesis_id}")
        unknown = sorted(set(record.observation_ids) - set(state.observations))
        if unknown:
            raise ValueError(f"unknown observations: {', '.join(unknown)}")
        self.repository.append(run_id, EventType.FALSIFICATION_RECORDED, record)
        self._advance(run_id, state.loop_state, LoopState.FALSIFYING, {LoopState.PARSING})
        return record

    def record_belief_update(
        self,
        run_id: str,
        update: BeliefUpdate,
        *,
        status: HypothesisStatus | None = None,
    ) -> Hypothesis:
        state = self.state(run_id)
        if not capabilities(state.run.mode).belief_posterior:
            raise ValueError(f"belief updates are disabled in {state.run.mode.value}")
        hypothesis = state.hypotheses.get(update.hypothesis_id)
        if hypothesis is None:
            raise ValueError(f"unknown hypothesis: {update.hypothesis_id}")
        invalid_observations = [
            identifier
            for identifier in update.observation_ids
            if identifier not in state.observations
            or state.observations[identifier].exit_status != "completed"
            or state.observations[identifier].failure_class is not None
        ]
        if invalid_observations:
            raise ValueError(f"failed or unknown observations cannot update beliefs: {invalid_observations}")
        self.repository.append(run_id, EventType.BELIEF_UPDATED, update)
        revised = hypothesis.model_copy(
            update={
                "current_confidence": update.posterior_confidence,
                "status": status or hypothesis.status,
                "version": hypothesis.version + 1,
                "evidence_for": sorted(set(hypothesis.evidence_for) | set(update.observation_ids))
                if update.evidence_strength > 0
                else hypothesis.evidence_for,
                "evidence_against": sorted(set(hypothesis.evidence_against) | set(update.observation_ids))
                if update.evidence_strength < 0
                else hypothesis.evidence_against,
            }
        )
        self.repository.append(run_id, EventType.HYPOTHESIS_REVISED, revised)
        self._advance(run_id, state.loop_state, LoopState.UPDATING, {LoopState.FALSIFYING})
        return revised

    def advance_phase(self, run_id: str, evidence: PhaseEvidence, *, next_state: LoopState | None = None) -> Phase:
        state = self.state(run_id)
        decided = decide_phase(state.phase, list(state.hypotheses.values()), evidence)
        self._advance(run_id, state.loop_state, LoopState.PHASE_DECISION, {LoopState.UPDATING})
        if decided != state.phase:
            self.repository.append(run_id, EventType.PHASE_CHANGED, {"phase": decided.value})
        if next_state is None and decided == Phase.EXPLOITATION and state.brief is None:
            # Exploitation may not begin before the research brief exists; the run parks in
            # phase_decision so `handoff_to_exploiter` is the only way forward.
            return decided
        target = next_state or (LoopState.PLANNING if state.hypotheses else LoopState.HYPOTHESIZING)
        self._advance(run_id, LoopState.PHASE_DECISION, target, {LoopState.PHASE_DECISION})
        return decided

    def handoff_to_exploiter(self, run_id: str, brief: ResearchBrief) -> ResearchBrief:
        """Publish the validated search space the exploiter is allowed to work inside.

        The hand-off is an event, not a conversation: everything the exploiter may assume is in the
        brief, and anything absent from it was not established by this run.
        """
        state = self.state(run_id)
        if state.phase != Phase.EXPLOITATION:
            raise LoopStateError(f"run is in {state.phase.value}; the exploiter hand-off requires exploitation")
        if brief.run_id != run_id:
            raise ValueError(f"brief belongs to run {brief.run_id}")
        self._advance(run_id, state.loop_state, LoopState.EXPLOITER_HANDOFF, {LoopState.PHASE_DECISION})
        self.repository.append(run_id, EventType.RESEARCH_BRIEF_CREATED, brief)
        self._advance(run_id, LoopState.EXPLOITER_HANDOFF, LoopState.PLANNING, {LoopState.EXPLOITER_HANDOFF})
        return brief

    def replan(self, run_id: str, reason: str) -> LoopState:
        """Return an unproductive round to planning instead of stalling in it.

        Selection can legitimately choose nothing — every candidate gated out, every utility below
        threshold. Without this the loop would sit in `selecting` with no work to dispatch and no way
        to propose different work, which is how an unattended run dies quietly.
        """
        state = self.state(run_id)
        allowed = {LoopState.SELECTING, LoopState.EXECUTING, LoopState.PARSING}
        if state.loop_state not in allowed:
            raise LoopStateError(f"cannot replan from {state.loop_state.value}")
        machine = ResearchStateMachine(state.loop_state)
        machine.transition(LoopState.PLANNING)
        self.repository.append(
            run_id,
            EventType.STATE_CHANGED,
            {"state": LoopState.PLANNING.value, "run_status": RunStatus.RUNNING.value, "reason": reason},
        )
        return LoopState.PLANNING

    def register_final_selection_rule(
        self,
        run_id: str,
        *,
        description: str,
        policy: Literal["final_candidate_utility_v1", "cross_fitted_ensemble_v1"] = "final_candidate_utility_v1",
    ) -> FinalSelectionRule:
        state = self.state(run_id)
        if state.final_selection_rule is not None:
            raise ValueError("the final candidate selection rule is already locked")
        if state.observations:
            raise ValueError("the final candidate selection rule must be registered before observing results")
        rule = FinalSelectionRule(
            id=f"FSR-{uuid.uuid4().hex[:12]}",
            run_id=run_id,
            description=description,
            policy=policy,
        )
        self.repository.append(run_id, EventType.FINAL_SELECTION_RULE_REGISTERED, rule)
        return rule

    def finalize(
        self,
        run_id: str,
        *,
        artifacts: Sequence[str],
        note: str,
        qd_maximum_size: int = 100,
        qd_quality_floor_relative_to_best: float = 0.97,
    ) -> dict[str, Any]:
        """Close the run and record what it is submitting as its answer.

        A final submission is not an experiment. It buys no information, it is the most expensive
        fit the run will make, and under an exploiter's pragmatic weights it scores negative utility
        and is refused by the very selector meant to choose research. `FINALIZING` existed in the
        state machine for exactly this and nothing ever entered it, so producing a final artifact
        had to happen outside the loop's accounting entirely. This is the path in.
        """
        state = self.state(run_id)
        allowed = {LoopState.PLANNING, LoopState.SELECTING, LoopState.PHASE_DECISION, LoopState.EXPLOITER_HANDOFF}
        if state.loop_state not in allowed:
            raise LoopStateError(f"cannot finalize from {state.loop_state.value}")
        if state.final_selection_rule is None:
            raise ValueError("the final candidate selection rule must be registered before finalization")
        if not note.strip():
            raise ValueError("final candidate selection rule/note must be fixed before locking")
        if not artifacts:
            raise ValueError("at least one final artifact is required")
        resolved = [Path(item).resolve() for item in artifacts]
        missing = [str(path) for path in resolved if not path.is_file()]
        if missing:
            raise ValueError(f"final artifacts are missing: {missing}")
        recorded = {
            Path(artifact.uri).resolve()
            for observation in state.observations.values()
            for artifact in observation.artifacts
        }
        unregistered = [str(path) for path in resolved if path not in recorded]
        if unregistered:
            raise ValueError(f"final artifacts must come from a recorded experiment: {unregistered}")
        artifact_refs = {
            Path(artifact.uri).resolve(): artifact
            for observation in state.observations.values()
            for artifact in observation.artifacts
        }
        for path in resolved:
            reference = artifact_refs[path]
            if file_sha256(path) != reference.sha256:
                raise ValueError(f"final artifact content changed after observation: {path}")
            if reference.dataset_fingerprint != state.run.dataset_fingerprint:
                raise ValueError(f"final artifact dataset hash does not match the run: {path}")
            if reference.code_commit_sha != state.run.base_commit_sha:
                raise ValueError(f"final artifact code commit does not match the run: {path}")
        submissions = [path for path in resolved if path.suffix.lower() == ".csv"]
        if not submissions:
            raise ValueError("a locked final candidate must include a CSV submission")
        for submission in submissions:
            with submission.open(newline="", encoding="utf-8") as file:
                reader = csv.reader(file)
                header = next(reader, [])
                row_count = 0
                invalid_row = False
                for row in reader:
                    row_count += 1
                    invalid_row = invalid_row or len(row) != len(header)
            if not header or len(header) != len(set(header)) or row_count == 0 or invalid_row:
                raise ValueError(f"invalid submission schema or empty submission: {submission}")
            if state.run.sample_submission:
                sample = Path(state.run.sample_submission)
                if not sample.is_file():
                    raise ValueError(f"sample submission is missing: {sample}")
                with sample.open(newline="", encoding="utf-8") as file:
                    sample_reader = csv.reader(file)
                    sample_header = next(sample_reader, [])
                    sample_row_count = sum(1 for _ in sample_reader)
                if header != sample_header:
                    raise ValueError(
                        f"submission columns {header} do not match sample submission columns {sample_header}"
                    )
                if row_count != sample_row_count:
                    raise ValueError(
                        f"submission row count {row_count} does not match sample submission row count "
                        f"{sample_row_count}"
                    )
        if capabilities(state.run.mode).belief_posterior and len(state.validation_worlds) < 2:
            raise ValueError("System C cannot lock before at least two validation worlds are recorded")
        public_queries = sum(
            event.event_type == EventType.LEADERBOARD_FEEDBACK_RECORDED
            for event in self.repository.event_store(run_id).read_all()
        )
        if public_queries > state.run.max_public_queries:
            raise ValueError("public leaderboard query limit was exceeded")
        final_candidate_ids: list[str] = []
        final_ensemble_id: str | None = None
        if capabilities(state.run.mode).solution_qd:
            if not state.qd_candidates:
                raise ValueError("QD-enabled modes cannot lock before a candidate enters the archive")
            archive = QDArchive.rebuild(
                state.qd_candidates.values(),
                descriptor_names=descriptor_names_for_mode(state.run.mode),
                maximum_size=qd_maximum_size,
                quality_floor_relative_to_best=qd_quality_floor_relative_to_best,
            )
            locked_hashes = {file_sha256(path) for path in resolved}
            if state.final_selection_rule.policy == "cross_fitted_ensemble_v1":
                if not state.oof_ensembles:
                    raise ValueError("the locked selection rule requires a cross-fitted OOF ensemble")
                ensemble = max(state.oof_ensembles.values(), key=lambda item: (item.marginal_gain, item.id))
                if not locked_hashes <= set(ensemble.artifact_ids):
                    raise ValueError("every locked artifact must belong to the selected OOF ensemble")
                if ensemble.marginal_gain <= 0:
                    raise ValueError("cross-fitted ensemble does not improve over the best single candidate")
                for candidate_id in ensemble.candidate_ids:
                    _validate_final_candidate(state, state.qd_candidates[candidate_id])
                locked_observations = [
                    observation
                    for observation in state.observations.values()
                    if any(Path(item.uri).resolve() in resolved for item in observation.artifacts)
                ]
                if not locked_observations or any(
                    state.proposals[observation.experiment_id].experiment_type != ExperimentType.ENSEMBLE
                    for observation in locked_observations
                ):
                    raise ValueError("locked OOF ensemble artifacts must come from ensemble experiments")
                if not any(_valid_replay_manifest(state, observation) for observation in locked_observations):
                    raise ValueError("the selected OOF ensemble has no replayable experiment manifest")
                if not any(
                    state.proposals[observation.experiment_id].implementation_request.get("command")
                    for observation in locked_observations
                ):
                    raise ValueError("the selected OOF ensemble has no saved submission procedure")
                final_candidate_ids.extend(ensemble.candidate_ids)
                final_ensemble_id = ensemble.id
            else:
                winner = select_final_candidate(archive.candidates)
                if not locked_hashes <= set(winner.artifact_ids):
                    raise ValueError(f"every locked artifact must belong to deterministic final candidate {winner.id}")
                _validate_final_candidate(state, winner)
                final_candidate_ids.append(winner.id)
        payload = {
            "run_id": run_id,
            "note": note,
            "artifacts": [{"uri": str(path), "sha256": file_sha256(path), "locked": True} for path in resolved],
            "phase": state.phase.value,
            "experiments_completed": sum(
                status == ExperimentStatus.COMPLETED for status in state.experiment_statuses.values()
            ),
            "observed_runtime": state.observed_runtime(),
            "dataset_fingerprint": state.run.dataset_fingerprint,
            "validation_world_posterior": {
                identifier: world.posterior_probability for identifier, world in state.validation_worlds.items()
            },
            "selection_rule_locked": True,
            "selection_rule": state.final_selection_rule.model_dump(mode="json"),
            "final_candidate_ids": final_candidate_ids,
            "final_ensemble_id": final_ensemble_id,
            "public_queries_used": public_queries,
        }
        self._advance(run_id, state.loop_state, LoopState.FINALIZING, allowed)
        self.repository.append(
            run_id,
            EventType.STATE_CHANGED,
            {"state": LoopState.COMPLETED.value, "run_status": RunStatus.COMPLETED.value},
        )
        self.repository.append(run_id, EventType.RUN_FINALIZED, payload)
        return payload

    # -------------------------------------------------------------- auditing

    def record_violation(self, run_id: str, violation: HoldoutViolation) -> None:
        self.repository.append(run_id, EventType.VIOLATION_DETECTED, violation)

    def record_leaderboard_feedback(self, run_id: str, payload: dict[str, Any]) -> None:
        self.repository.append(run_id, EventType.LEADERBOARD_FEEDBACK_RECORDED, payload)

    # ---------------------------------------------------- validation / QD / OOF

    def record_validation_worlds(self, run_id: str, worlds: Sequence[ValidationWorld]) -> list[str]:
        state = self.state(run_id)
        if state.validation_worlds:
            raise ValueError("validation worlds have already been initialized for this run")
        incoming = list(worlds)
        if any(item.run_id != run_id for item in incoming):
            raise ValueError("validation worlds must belong to the current run")
        validate_world_distribution(incoming)
        for world in incoming:
            self.repository.append(run_id, EventType.VALIDATION_WORLD_REGISTERED, world)
        return [item.id for item in incoming]

    def update_validation_posterior(self, run_id: str, evidence: ValidationWorldEvidence) -> dict[str, float]:
        state = self.state(run_id)
        if evidence.run_id != run_id:
            raise ValueError("validation evidence belongs to another run")
        if evidence.observation_id not in state.observations:
            raise ValueError(f"unknown observation: {evidence.observation_id}")
        _, update = update_worlds(list(state.validation_worlds.values()), evidence)
        self.repository.append(run_id, EventType.VALIDATION_EVIDENCE_RECORDED, evidence)
        self.repository.append(run_id, EventType.VALIDATION_POSTERIOR_UPDATED, update)
        return update.posterior

    def propose_falsification(
        self,
        run_id: str,
        *,
        available_data: Sequence[str],
        proposer_agent: str = "independent-falsifier",
    ) -> FalsificationProposal:
        state = self.state(run_id)
        if not capabilities(state.run.mode).independent_falsifier:
            raise ValueError(f"independent falsification is disabled in {state.run.mode.value}")
        remaining = BudgetManager(state.run.budgets, state.usage).remaining()
        proposal = Falsifier().propose(
            list(state.hypotheses.values()),
            available_data=available_data,
            remaining_cpu_hours=float(remaining["cpu_hours"]),
            proposer_agent=proposer_agent,
        )
        self.repository.append(run_id, EventType.FALSIFICATION_PROPOSED, proposal)
        return proposal

    def archive_candidate(
        self,
        run_id: str,
        candidate: QDCandidate,
        *,
        maximum_size: int = 100,
        quality_floor_relative_to_best: float = 0.97,
    ) -> ArchiveUpdate:
        state = self.state(run_id)
        descriptor_names = descriptor_names_for_mode(state.run.mode)
        if not descriptor_names:
            raise ValueError(f"QD archive is disabled in {state.run.mode.value}")
        if candidate.run_id != run_id:
            raise ValueError("QD candidate belongs to another run")
        if candidate.id in state.qd_candidates:
            raise ValueError(f"QD candidate {candidate.id} has already been evaluated")
        if candidate.experiment_id not in state.proposals:
            raise ValueError(f"unknown experiment: {candidate.experiment_id}")
        if not any(
            observation.experiment_id == candidate.experiment_id and observation.exit_status == "completed"
            for observation in state.observations.values()
        ):
            raise ValueError("a QD candidate requires a completed experiment observation")
        archive = QDArchive.rebuild(
            state.qd_candidates.values(),
            descriptor_names=descriptor_names,
            maximum_size=maximum_size,
            quality_floor_relative_to_best=quality_floor_relative_to_best,
        )
        update = archive.add(candidate)
        self.repository.append(run_id, EventType.QD_CANDIDATE_EVALUATED, candidate)
        return update

    def record_oof_artifact(self, run_id: str, artifact: OOFArtifact) -> None:
        state = self.state(run_id)
        if not capabilities(state.run.mode).oof_diversity:
            raise ValueError(f"OOF diversity is disabled in {state.run.mode.value}")
        if artifact.run_id != run_id:
            raise ValueError("OOF artifact belongs to another run")
        if artifact.candidate_id not in state.qd_candidates:
            raise ValueError(f"unknown QD candidate: {artifact.candidate_id}")
        if artifact.id in state.oof_artifacts:
            raise ValueError(f"OOF artifact {artifact.id} already exists")
        path = Path(artifact.uri)
        if not path.is_file() or file_sha256(path) != artifact.sha256:
            raise ValueError("OOF artifact is missing or its SHA-256 does not match")
        self.repository.append(run_id, EventType.OOF_ARTIFACT_RECORDED, artifact)

    def record_oof_analysis(self, run_id: str, payload: dict[str, Any]) -> None:
        state = self.state(run_id)
        identifiers = set(payload.get("candidate_ids", []))
        if not identifiers or not identifiers <= set(state.qd_candidates):
            raise ValueError("OOF analysis must reference recorded QD candidates")
        correlations: dict[str, list[float]] = {identifier: [] for identifier in identifiers}
        for pair, value in payload.get("residual_correlations", {}).items():
            left, separator, right = str(pair).partition("::")
            if not separator or left not in correlations or right not in correlations:
                raise ValueError(f"invalid OOF residual-correlation pair: {pair}")
            correlations[left].append(float(value))
            correlations[right].append(float(value))
        self.repository.append(run_id, EventType.OOF_ANALYSIS_RECORDED, payload)
        for identifier, values in correlations.items():
            if not values:
                continue
            diversity = sum(1 - abs(value) for value in values) / len(values)
            candidate = state.qd_candidates[identifier]
            revised = candidate.model_copy(update={"error_diversity": max(candidate.error_diversity, diversity)})
            self.repository.append(run_id, EventType.QD_CANDIDATE_EVALUATED, revised)

    def record_oof_ensemble(
        self,
        run_id: str,
        ensemble: OOFEnsemble,
        *,
        qd_maximum_size: int = 100,
        qd_quality_floor_relative_to_best: float = 0.97,
    ) -> None:
        state = self.state(run_id)
        if not capabilities(state.run.mode).oof_diversity:
            raise ValueError(f"OOF ensembles are disabled in {state.run.mode.value}")
        if ensemble.run_id != run_id:
            raise ValueError("OOF ensemble belongs to another run")
        if ensemble.id in state.oof_ensembles:
            raise ValueError(f"OOF ensemble {ensemble.id} already exists")
        if not set(ensemble.candidate_ids) <= set(state.qd_candidates):
            raise ValueError("OOF ensemble references unknown QD candidates")
        retained = {
            item.id
            for item in state.retained_qd_candidates(
                maximum_size=qd_maximum_size,
                quality_floor_relative_to_best=qd_quality_floor_relative_to_best,
            )
        }
        if not set(ensemble.candidate_ids) <= retained:
            raise ValueError("OOF ensemble members must satisfy the retained QD quality frontier")
        artifact_candidates = {
            artifact.candidate_id
            for artifact in state.oof_artifacts.values()
            if artifact.validation_world == ensemble.validation_world
        }
        if not set(ensemble.candidate_ids) <= artifact_candidates:
            raise ValueError("every ensemble member needs a recorded OOF artifact for the validation world")
        recorded_hashes = {
            artifact.sha256 for observation in state.observations.values() for artifact in observation.artifacts
        }
        if not set(ensemble.artifact_ids) <= recorded_hashes:
            raise ValueError("OOF ensemble output artifacts must come from recorded observations")
        self.repository.append(run_id, EventType.OOF_ENSEMBLE_CREATED, ensemble)


def _validate_final_candidate(state: RunState, candidate: QDCandidate) -> None:
    successful_replications = [
        proposal
        for proposal in state.proposals.values()
        if proposal.experiment_type == ExperimentType.REPLICATION
        and proposal.is_replication_of == candidate.experiment_id
        and state.experiment_statuses.get(proposal.id) == ExperimentStatus.COMPLETED
        and any(
            observation.experiment_id == proposal.id
            and observation.exit_status == "completed"
            and observation.failure_class is None
            and observation.code_commit_sha == state.run.base_commit_sha
            and observation.dataset_fingerprint == state.run.dataset_fingerprint
            and observation.metrics.get("reproduction_passed", 0.0) >= 1.0
            for observation in state.observations.values()
        )
    ]
    if not successful_replications:
        raise ValueError(f"final candidate {candidate.id} has no successful independent replication")
    if not candidate.leakage_check_passed:
        raise ValueError(f"final candidate {candidate.id} has not passed leakage checks")
    if candidate.fold_assignment_artifact is None:
        raise ValueError(f"final candidate {candidate.id} has no saved fold assignment")
    candidate_oof_artifacts = [item for item in state.oof_artifacts.values() if item.candidate_id == candidate.id]
    if not candidate_oof_artifacts:
        raise ValueError(f"final candidate {candidate.id} has no recorded OOF artifact")
    observations = [item for item in state.observations.values() if item.experiment_id == candidate.experiment_id]
    fold_path = Path(candidate.fold_assignment_artifact).resolve()
    fold_artifact = next(
        (
            artifact
            for observation in observations
            for artifact in observation.artifacts
            if Path(artifact.uri).resolve() == fold_path
        ),
        None,
    )
    if fold_artifact is None or not fold_path.is_file() or file_sha256(fold_path) != fold_artifact.sha256:
        raise ValueError(f"final candidate {candidate.id} fold assignment is missing or changed")
    if not any(Path(item.uri).is_file() and file_sha256(item.uri) == item.sha256 for item in candidate_oof_artifacts):
        raise ValueError(f"final candidate {candidate.id} OOF artifact is missing or changed")
    manifests = [manifest for item in observations if (manifest := _valid_replay_manifest(state, item)) is not None]
    if not manifests:
        raise ValueError(f"final candidate {candidate.id} has no replayable experiment manifest")
    if not any(fold_path in {Path(item).resolve() for item in manifest.fold_assignment_refs} for manifest in manifests):
        raise ValueError(f"final candidate {candidate.id} manifest does not record its fold assignment")
    if not candidate.submission_procedure:
        raise ValueError(f"final candidate {candidate.id} has no saved submission procedure")


def _valid_replay_manifest(state: RunState, observation: Observation) -> ExperimentManifest | None:
    if not observation.manifest_ref:
        return None
    path = Path(observation.manifest_ref)
    if not path.is_file():
        return None
    try:
        manifest = ExperimentManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except ValueError:
        return None
    request = manifest.request
    result = manifest.result
    if (
        manifest.run_id != state.run_id
        or manifest.experiment_id != observation.experiment_id
        or manifest.system_mode != state.run.mode
        or request.base_commit_sha != state.run.base_commit_sha
        or request.config_hash != state.run.config_hash
        or request.dataset_fingerprint != state.run.dataset_fingerprint
        or result.commit_sha != state.run.base_commit_sha
        or result.dataset_fingerprint != state.run.dataset_fingerprint
        or result.environment_hash != observation.environment_hash
        or manifest.environment_lock_hash != result.environment_lock_hash
        or manifest.environment_lock_ref is None
        or not Path(manifest.environment_lock_ref).is_file()
    ):
        return None
    environment_path = Path(manifest.environment_lock_ref).resolve()
    manifest_artifact = next(
        (item for item in observation.artifacts if Path(item.uri).resolve() == path.resolve()),
        None,
    )
    environment_artifact = next(
        (item for item in observation.artifacts if Path(item.uri).resolve() == environment_path),
        None,
    )
    if (
        manifest_artifact is None
        or file_sha256(path) != manifest_artifact.sha256
        or environment_artifact is None
        or file_sha256(environment_path) != environment_artifact.sha256
    ):
        return None
    return manifest


def _rejected_reasons(
    scored: Sequence[ScoredCandidate],
    selected: Sequence[ScoredCandidate],
    minimum_utility: float,
) -> dict[str, list[str]]:
    """Gate failures and below-threshold utility are terminal; merely unselected stays proposed."""
    chosen = {item.proposal.id for item in selected}
    rejected: dict[str, list[str]] = {}
    for item in scored:
        if item.proposal.id in chosen:
            continue
        if not item.gate.passed:
            rejected[item.proposal.id] = list(item.gate.reasons)
        elif item.utility is not None and item.utility.total < minimum_utility:
            rejected[item.proposal.id] = [f"utility {item.utility.total:.4f} is below {minimum_utility:.4f}"]
    return rejected


def _posterior_weighted_metric(state: RunState, observation: Observation) -> float | None:
    """Use all validation worlds when the worker reports them, else the primary metric."""

    worlds = list(state.validation_worlds.values())
    world_scores: dict[str, float] = {}
    for world in worlds:
        value = next(
            (
                observation.metrics[key]
                for key in (
                    f"{state.run.primary_metric}@{world.id}",
                    f"{state.run.primary_metric}:{world.id}",
                )
                if key in observation.metrics
            ),
            None,
        )
        if value is not None:
            world_scores[world.id] = value
    if worlds and len(world_scores) == len(worlds):
        return expected_score(worlds, world_scores)
    return observation.metrics.get(state.run.primary_metric)


def _require_experiment(state: RunState, experiment_id: str) -> ExperimentProposal:
    proposal = state.proposals.get(experiment_id)
    if proposal is None:
        raise ValueError(f"unknown experiment: {experiment_id}")
    return proposal


def _artifact_refs(
    result: ExperimentResult,
    *,
    run: ResearchRun,
    proposal: ExperimentProposal,
) -> list[ArtifactRef]:
    refs: list[ArtifactRef] = []
    for reference in result.artifact_refs:
        path = Path(reference)
        if not path.is_file():
            continue
        refs.append(
            ArtifactRef(
                uri=str(path),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                experiment_id=result.experiment_id,
                code_commit_sha=result.commit_sha,
                dataset_fingerprint=result.dataset_fingerprint,
                environment_hash=result.environment_hash,
                content_address_sha256=_content_address(result, run, proposal),
                config_hash=run.config_hash,
                random_seeds=proposal.seeds,
                mime_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                size=path.stat().st_size,
            )
        )
    return refs


def _sidecar(root: Path | None, name: str) -> dict[str, Any]:
    if root is None:
        return {}
    path = root / name
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {"value": value}


def _observation_from_result(
    result: ExperimentResult,
    artifact_root: str | Path | None,
    *,
    run: ResearchRun,
    proposal: ExperimentProposal,
) -> Observation:
    root = Path(artifact_root) if artifact_root is not None else None
    return Observation(
        id=f"OB-{uuid.uuid4().hex[:12]}",
        experiment_id=result.experiment_id,
        run_id=result.run_id,
        metrics=dict(result.metrics),
        observed_outcomes=dict(result.observed_outcomes),
        code_commit_sha=result.commit_sha,
        environment_hash=result.environment_hash,
        dataset_fingerprint=result.dataset_fingerprint,
        artifacts=_artifact_refs(result, run=run, proposal=proposal),
        runtime=dict(result.runtime),
        resource_usage=result.resource_usage,
        manifest_ref=result.manifest_ref,
        exit_status=result.status,
        failure_class=result.failure_class,
        failure_excerpt=result.failure_excerpt,
        fold_metrics=_sidecar(root, SIDECAR_METRICS["fold_metrics"]),
        seed_metrics=_sidecar(root, SIDECAR_METRICS["seed_metrics"]),
        subgroup_metrics=_sidecar(root, SIDECAR_METRICS["subgroup_metrics"]),
    )


def _content_address(result: ExperimentResult, run: ResearchRun, proposal: ExperimentProposal) -> str:
    components = (
        result.commit_sha,
        run.config_hash,
        result.dataset_fingerprint,
        result.environment_hash,
        ",".join(str(seed) for seed in proposal.seeds),
    )
    return hashlib.sha256("".join(components).encode()).hexdigest()


def _resource_reconciliation(
    state: RunState,
    proposal: ExperimentProposal,
    result: ExperimentResult,
) -> ResourceReconciliation:
    observed = result.resource_usage
    wall_hours = observed.wall_hours
    if wall_hours is None:
        if "wall_hours" in result.runtime:
            wall_hours = float(result.runtime["wall_hours"])
        elif "wall_seconds" in result.runtime:
            wall_hours = float(result.runtime["wall_seconds"]) / 3600
    estimated = proposal.estimated_cost
    charged = CostEstimate(
        cpu_hours=observed.cpu_hours if observed.cpu_hours is not None else estimated.cpu_hours,
        gpu_hours=observed.gpu_hours if observed.gpu_hours is not None else estimated.gpu_hours,
        wall_hours=wall_hours if wall_hours is not None else estimated.wall_hours,
        llm_tokens=observed.llm_tokens if observed.llm_tokens is not None else estimated.llm_tokens,
        monetary_cost=(observed.monetary_cost if observed.monetary_cost is not None else estimated.monetary_cost),
        failure_probability=estimated.failure_probability,
    )
    return ResourceReconciliation(
        run_id=state.run_id,
        experiment_id=result.experiment_id,
        estimated=estimated,
        observed=observed,
        charged=charged,
    )


def _forecast_calibrations(
    state: RunState,
    proposal: ExperimentProposal,
    result: ExperimentResult,
) -> list[ForecastCalibrationRecord]:
    if result.status != "completed" or result.failure_class is not None:
        return []
    interval_coverage: dict[str, bool] = {}
    for prediction in proposal.predicted_outcomes:
        value = result.metrics.get(prediction.metric_name)
        expected = prediction.expected_range or {}
        lower = expected.get("lower", expected.get("min"))
        upper = expected.get("upper", expected.get("max"))
        if value is not None and lower is not None and upper is not None and prediction.coverage_level is not None:
            interval_coverage[str(prediction.coverage_level)] = lower <= value <= upper
    records: list[ForecastCalibrationRecord] = []
    for forecast in proposal.outcome_forecasts:
        observed = result.observed_outcomes.get(forecast.hypothesis_id)
        hypothesis = state.hypotheses.get(forecast.hypothesis_id)
        if observed is None or hypothesis is None:
            continue
        prior = hypothesis.current_confidence
        probabilities = {
            outcome.label: prior * outcome.probability_if_true + (1 - prior) * outcome.probability_if_false
            for outcome in forecast.outcomes
        }
        records.append(
            ForecastCalibrationRecord(
                id=f"FCR-{uuid.uuid4().hex[:12]}",
                run_id=state.run_id,
                experiment_id=proposal.id,
                proposer_agent=proposal.proposer_agent,
                category=hypothesis.type.value,
                probabilities=probabilities,
                observed_label=observed,
                interval_coverage=interval_coverage,
            )
        )
    validation_forecast = proposal.validation_world_forecast
    validation_label = result.observed_outcomes.get("validation_world")
    if validation_forecast is not None and validation_label is not None and state.validation_worlds:
        probabilities = {
            outcome.label: sum(
                state.validation_worlds[world_id].posterior_probability * probability
                for world_id, probability in outcome.probability_by_world.items()
            )
            for outcome in validation_forecast.outcomes
        }
        records.append(
            ForecastCalibrationRecord(
                id=f"FCR-{uuid.uuid4().hex[:12]}",
                run_id=state.run_id,
                experiment_id=proposal.id,
                proposer_agent=proposal.proposer_agent,
                category="validation_world",
                probabilities=probabilities,
                observed_label=validation_label,
                interval_coverage=interval_coverage,
            )
        )
    return records


def _shrink_uncalibrated_prior(
    hypothesis: Hypothesis,
    state: RunState,
    *,
    minimum_records: int,
    poor_brier_threshold: float,
    prior_shrinkage: float,
) -> Hypothesis:
    if not capabilities(state.run.mode).belief_posterior or not 0 < prior_shrinkage <= 1:
        return hypothesis
    relevant = [
        item
        for item in state.forecast_calibrations
        if item.proposer_agent == hypothesis.created_by or item.category == hypothesis.type.value
    ]
    if len(relevant) < minimum_records:
        return hypothesis
    summary = summarize_calibration(relevant)
    if summary.brier_score <= poor_brier_threshold:
        return hypothesis
    proposed = hypothesis.prior_confidence
    shrunk = 0.5 + (proposed - 0.5) * (1 - prior_shrinkage)
    return hypothesis.model_copy(
        update={
            "prior_confidence": shrunk,
            "current_confidence": shrunk,
            "uncalibrated_prior_confidence": proposed,
        }
    )


def fingerprint_path(path: str | Path | None) -> str:
    if path is None:
        return hashlib.sha256(b"unavailable").hexdigest()
    target = Path(path)
    if not target.exists():
        return hashlib.sha256(f"missing:{target}".encode()).hexdigest()
    digest = hashlib.sha256()
    paths = sorted(target.rglob("*")) if target.is_dir() else [target]
    for item in paths:
        if not item.is_file():
            continue
        digest.update(str(item.relative_to(target) if target.is_dir() else item.name).encode())
        with item.open("rb") as file:
            for block in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()


def file_sha256(path: str | Path) -> str:
    target = Path(path)
    if not target.is_file():
        raise ValueError(f"artifact is not a file: {target}")
    digest = hashlib.sha256()
    with target.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
