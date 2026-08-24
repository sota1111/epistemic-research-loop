from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from epistemic_loop.adapters.executor.base import ExecutorAdapter, result_path
from epistemic_loop.agents.auto import AutomaticProposer
from epistemic_loop.agents.belief_interpreter import DISPOSITION_STATUS, interpret_evidence
from epistemic_loop.agents.falsifier import Falsifier
from epistemic_loop.agents.research_synthesizer import derive_brief
from epistemic_loop.belief.updater import belief_update
from epistemic_loop.config import AppConfig
from epistemic_loop.controller.phase_evidence import derive_phase_evidence
from epistemic_loop.controller.research_graph import ResearchController
from epistemic_loop.controller.stop_policy import should_stop
from epistemic_loop.domain.enums import ExperimentStatus, LoopState, Phase
from epistemic_loop.domain.events import EventType
from epistemic_loop.domain.models import (
    CompetitionWorldModel,
    ExperimentResult,
    FalsificationRecord,
    Observation,
)


@dataclass(frozen=True)
class LoopSettings:
    rounds: int = 1
    portfolio_size: int = 1
    poll_seconds: float = 10.0
    timeout_seconds: float = 3600.0


@dataclass
class RoundOutcome:
    round: int
    hypotheses: list[str] = field(default_factory=list)
    experiments: list[str] = field(default_factory=list)
    selected: list[str] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)
    beliefs: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    phase: str = Phase.DISCOVERY.value
    brief_created: bool = False
    replanned: str | None = None
    stop_reasons: list[str] = field(default_factory=list)


class AutonomousLoop:
    """Runs the full cycle without human hand-off.

    The LLM is consulted at exactly three points — propose hypotheses, design experiments, judge
    which predictions the evidence matched. Gates, utility, selection, budgets, dispositions, and
    the belief arithmetic stay deterministic, so automation changes who fills the proposal slots,
    not who decides what counts as evidence.
    """

    def __init__(
        self,
        controller: ResearchController,
        proposer: AutomaticProposer,
        executor: ExecutorAdapter,
        *,
        config: AppConfig,
        home: str | Path = ".",
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], float] = time.monotonic,
    ):
        self.controller = controller
        self.proposer = proposer
        self.executor = executor
        self.config = config
        self.home = Path(home)
        self.sleep = sleep
        self.now = now
        self._quiet_rounds = 0

    # ------------------------------------------------------------- helpers

    def _world_model(self, run_id: str) -> CompetitionWorldModel:
        events = self.controller.repository.event_store(run_id).read_all()
        payload = next(
            (event.payload for event in reversed(events) if event.event_type == EventType.WORLD_MODEL_RECORDED),
            None,
        )
        if payload is None:
            raise ValueError(f"run {run_id} has no world model; start the run first")
        return CompetitionWorldModel.model_validate(payload)

    def _await_result(self, run_id: str, experiment_id: str, settings: LoopSettings) -> ExperimentResult | None:
        source = result_path(self.home / self.config.executor.result_root, run_id, experiment_id)
        deadline = self.now() + settings.timeout_seconds
        while True:
            if source.is_file():
                result = ExperimentResult.model_validate_json(source.read_text(encoding="utf-8"))
                if result.status in {"completed", "failed"}:
                    return result
            if self.now() >= deadline:
                return None
            self.sleep(settings.poll_seconds)

    def _interpret(self, run_id: str, observations: list[Observation], outcome: RoundOutcome) -> None:
        """Falsify every touched hypothesis first, then update every belief.

        The state machine allows `parsing -> falsifying -> updating` once per round, so the two
        passes cannot be interleaved per hypothesis.
        """
        state = self.controller.state(run_id)
        pairs = []
        for observation in observations:
            proposal = state.proposals.get(observation.experiment_id)
            if proposal is None:
                continue
            for hypothesis_id in proposal.hypothesis_ids:
                hypothesis = state.hypotheses.get(hypothesis_id)
                if hypothesis is not None:
                    pairs.append((hypothesis, [observation], proposal))

        assessments = []
        for hypothesis, linked, proposal in pairs:
            assessment = self.proposer.assess(run_id, hypothesis, linked, proposal)
            record: FalsificationRecord = Falsifier().record(
                hypothesis,
                linked,
                supporting_predictions=assessment.supporting_predictions,
                contradicting_predictions=assessment.contradicting_predictions,
                alternative_explanation=assessment.alternative_explanation,
                confounders_checked=assessment.confounders_checked,
                recommended_next_test=assessment.recommended_next_test,
                alternative_claims=assessment.alternative_claims,
            )
            self.controller.record_falsification(run_id, record)
            assessments.append((hypothesis, record, assessment, [item.id for item in linked]))

        for hypothesis, record, assessment, observation_ids in assessments:
            current = self.controller.state(run_id).hypotheses[hypothesis.id]
            update = belief_update(
                hypothesis.id,
                current.current_confidence,
                interpret_evidence(record),
                assessment.evidence_summary,
                observation_ids,
                assessment.verifier_result,
            )
            self.controller.record_belief_update(run_id, update, status=DISPOSITION_STATUS[record.disposition])
            outcome.beliefs.append(hypothesis.id)

    # ---------------------------------------------------------------- rounds

    def _dispatch_and_collect(self, run_id: str, settings: LoopSettings, outcome: RoundOutcome) -> None:
        state = self.controller.state(run_id)
        for proposal in state.experiments_with_status(ExperimentStatus.SELECTED):
            self.controller.dispatch(
                run_id,
                proposal.id,
                self.executor,
                container_image=self.config.executor.container_image,
                dataset_mounts=self.config.executor.dataset_mounts,
                network_policy=self.config.contamination.worker_network,
            )
        running = [item.id for item in self.controller.state(run_id).experiments_with_status(ExperimentStatus.RUNNING)]
        for experiment_id in running:
            result = self._await_result(run_id, experiment_id, settings)
            if result is None:
                outcome.pending.append(experiment_id)
                continue
            observation = self.controller.import_result(
                run_id,
                result,
                artifact_root=result_path(self.home / self.config.executor.result_root, run_id, experiment_id).parent,
            )
            if observation is not None:
                outcome.observations.append(observation.id)

    def run_round(self, run_id: str, index: int, settings: LoopSettings) -> RoundOutcome:
        """Advance the run by one round, resuming from whatever state it was left in.

        An unattended loop must survive an interrupted round — a worker that never reported, a
        control-plane hand-off that failed — so each stage is entered from the recorded state
        rather than from the assumption that this process started the round.
        """
        outcome = RoundOutcome(round=index)
        state = self.controller.state(run_id)

        if state.loop_state == LoopState.HYPOTHESIZING:
            proposed = self.proposer.hypotheses(
                run_id,
                self._world_model(run_id),
                state,
                maximum=self.config.loop.max_active_hypotheses,
            )
            outcome.hypotheses = self.controller.record_hypotheses(
                run_id, proposed, max_active=self.config.loop.max_active_hypotheses
            )
            state = self.controller.state(run_id)

        if state.loop_state == LoopState.PLANNING:
            outcome.experiments = self.controller.record_proposals(run_id, self.proposer.experiments(run_id, state))
            state = self.controller.state(run_id)

        utilities: list[float] = []
        if state.loop_state == LoopState.SCORING:
            decision = self.controller.select_experiments(
                run_id,
                weights=self.config.selection.for_phase(state.phase),
                cost_lambda=self.config.selection.cost_lambda,
                size=settings.portfolio_size,
                minimum_utility=self.config.selection.minimum_utility,
                source_policy_strict=self.config.contamination.require_source_provenance,
                max_validation_reuse=self.config.loop.max_validation_reuse,
                max_consecutive_optimization=self.config.loop.max_consecutive_optimization_experiments,
            )
            outcome.selected = list(decision.selected_experiment_ids)
            utilities = [
                value["total"]
                for value in decision.utility_breakdown.values()
                if isinstance(value, dict) and "total" in value
            ]
            if not outcome.selected:
                # Nothing survived the gates or the utility floor. Returning to planning lets the
                # next round propose different work; staying in `selecting` would stall the run.
                outcome.replanned = "no candidate passed selection"
                self.controller.replan(run_id, outcome.replanned)
                return self._finish(run_id, outcome, utilities)
            state = self.controller.state(run_id)

        if state.loop_state in {LoopState.SELECTING, LoopState.EXECUTING}:
            self._dispatch_and_collect(run_id, settings, outcome)
            state = self.controller.state(run_id)

        if state.loop_state in {LoopState.PARSING, LoopState.FALSIFYING}:
            pending = state.unjudged_observations()
            if pending:
                self._interpret(run_id, pending, outcome)
                state = self.controller.state(run_id)

        if state.loop_state == LoopState.UPDATING:
            evidence = derive_phase_evidence(
                state,
                instability_threshold=self.config.loop.anomaly_instability_threshold,
            )
            outcome.phase = self.controller.advance_phase(run_id, evidence).value
        else:
            outcome.phase = state.phase.value

        outcome.brief_created = self._handoff_if_due(run_id)
        return self._finish(run_id, outcome, utilities)

    def _handoff_if_due(self, run_id: str) -> bool:
        """Publish the research brief the first time the run reaches exploitation.

        `advance_phase` parks the run in `phase_decision` when exploitation is decided and no brief
        exists, so this is the step that actually opens exploitation — and it is derived from the
        event log, never asked of the model.
        """
        state = self.controller.state(run_id)
        if state.phase != Phase.EXPLOITATION or state.brief is not None:
            return False
        if state.loop_state != LoopState.PHASE_DECISION:
            return False
        brief = derive_brief(state, primary_metric=self.config.competition.primary_metric)
        self.controller.handoff_to_exploiter(run_id, brief)
        return True

    def _finish(self, run_id: str, outcome: RoundOutcome, utilities: list[float]) -> RoundOutcome:
        final = self.controller.state(run_id)
        outcome.phase = final.phase.value
        stop = should_stop(
            final.run.budgets,
            final.usage,
            maximum_candidate_utility=max(utilities) if utilities else None,
            minimum_utility=self.config.selection.minimum_utility,
            rounds_without_information=self._quiet_rounds,
            max_rounds_without_information=self.config.loop.max_rounds_without_information,
            holdout_violation=final.violations > 0,
        )
        outcome.stop_reasons = list(stop.reasons)
        return outcome

    def run(self, run_id: str, settings: LoopSettings) -> list[RoundOutcome]:
        """Run rounds until the budget, the stop policy, or a stuck worker ends the run.

        A round that produced no observation is counted, not ignored: three of them in a row means
        the loop is proposing work the gates keep refusing, and spinning is worse than stopping.
        """
        outcomes: list[RoundOutcome] = []
        self._quiet_rounds = 0
        for index in range(1, settings.rounds + 1):
            outcome = self.run_round(run_id, index, settings)
            self._quiet_rounds = 0 if outcome.observations else self._quiet_rounds + 1
            outcomes.append(outcome)
            if outcome.stop_reasons or outcome.pending:
                break
        return outcomes
