from __future__ import annotations

import hashlib
import json
import mimetypes
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from epistemic_loop.adapters.executor.base import ExecutorAdapter
from epistemic_loop.agents.experiment_designer import validate_preregistration
from epistemic_loop.agents.hypothesis_generator import validate_generated_hypotheses
from epistemic_loop.config import AppConfig, PhaseWeights, config_hash
from epistemic_loop.controller.budget_manager import BudgetManager
from epistemic_loop.controller.execution_contract import build_experiment_request
from epistemic_loop.controller.phase_policy import PhaseEvidence, decide_phase
from epistemic_loop.controller.run_state import RunState, load_run_state
from epistemic_loop.controller.state_machine import ResearchStateMachine
from epistemic_loop.domain.enums import (
    ExperimentStatus,
    HypothesisStatus,
    LoopState,
    Phase,
    RunStatus,
)
from epistemic_loop.domain.events import EventType
from epistemic_loop.domain.models import (
    ArtifactRef,
    BeliefUpdate,
    CompetitionWorldModel,
    DecisionRecord,
    ExperimentProposal,
    ExperimentRequest,
    ExperimentResult,
    FalsificationRecord,
    Hypothesis,
    Observation,
    ResearchBrief,
    ResearchRun,
)
from epistemic_loop.holdout.violations import HoldoutViolation
from epistemic_loop.scoring.selector import ScoredCandidate, evaluate_candidates, select_portfolio
from epistemic_loop.storage.repositories import ResearchRepository

POLICY_VERSION = "selection/v1"
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
        identifier = run_id or config.run.id or f"{config.competition.slug}-{uuid.uuid4().hex[:8]}"
        run = ResearchRun(
            id=identifier,
            competition_id=config.competition.slug,
            mode=config.run.mode,
            phase=Phase.DISCOVERY,
            seed=config.run.seed,
            status=RunStatus.CREATED,
            base_commit_sha=base_commit_sha,
            dataset_fingerprint=dataset_fingerprint,
            config_hash=config_hash(config),
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

    def record_hypotheses(self, run_id: str, hypotheses: Sequence[Hypothesis], *, max_active: int = 30) -> list[str]:
        state = self.state(run_id)
        incoming = list(hypotheses)
        for hypothesis in incoming:
            if hypothesis.run_id != run_id:
                raise ValueError(f"hypothesis {hypothesis.id} belongs to run {hypothesis.run_id}")
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

    def record_proposals(self, run_id: str, proposals: Sequence[ExperimentProposal]) -> list[str]:
        state = self.state(run_id)
        incoming = list(proposals)
        for proposal in incoming:
            if proposal.run_id != run_id:
                raise ValueError(f"experiment {proposal.id} belongs to run {proposal.run_id}")
            if proposal.id in state.proposals:
                raise ValueError(f"experiment {proposal.id} was already proposed")
            validate_preregistration(proposal)
            self.repository.append(run_id, EventType.EXPERIMENT_PROPOSED, proposal)
        self._advance(run_id, state.loop_state, LoopState.SCORING, {LoopState.PLANNING})
        return [item.id for item in incoming]

    def select_experiments(
        self,
        run_id: str,
        *,
        weights: PhaseWeights,
        cost_lambda: float = 0.15,
        size: int = 1,
        minimum_utility: float = float("-inf"),
        similarity_penalty: float = 0.25,
        source_policy_strict: bool = True,
        max_validation_reuse: int = 0,
    ) -> DecisionRecord:
        state = self.state(run_id)
        candidates = state.open_candidates()
        if not candidates:
            raise ValueError("no proposed experiments are available for selection")
        scored = evaluate_candidates(
            candidates,
            state.gate_context(
                source_policy_strict=source_policy_strict,
                max_validation_reuse=max_validation_reuse,
            ),
            weights,
            cost_lambda,
        )
        selected = select_portfolio(
            scored,
            size,
            similarity_penalty=similarity_penalty,
            minimum_utility=minimum_utility,
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
        request = build_experiment_request(
            state.run,
            proposal,
            attempt=attempt,
            container_image=container_image,
            dataset_mounts=dataset_mounts,
            network_policy=network_policy,
        )
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
        self._advance(run_id, state.loop_state, LoopState.EXECUTING, {LoopState.SELECTING})
        return request, executor.submit(request)

    def import_result(
        self,
        run_id: str,
        result: ExperimentResult,
        *,
        artifact_root: str | Path | None = None,
    ) -> Observation | None:
        state = self.state(run_id)
        _require_experiment(state, result.experiment_id)
        if result.status in {"queued", "running"}:
            return None
        completed = result.status == "completed"
        self.repository.append(
            run_id,
            EventType.EXPERIMENT_COMPLETED if completed else EventType.EXPERIMENT_FAILED,
            result,
        )
        observation = _observation_from_result(result, artifact_root)
        self.repository.append(run_id, EventType.OBSERVATION_RECORDED, observation)
        self._advance(run_id, state.loop_state, LoopState.PARSING, {LoopState.EXECUTING})
        return observation

    def record_falsification(self, run_id: str, record: FalsificationRecord) -> FalsificationRecord:
        state = self.state(run_id)
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
        hypothesis = state.hypotheses.get(update.hypothesis_id)
        if hypothesis is None:
            raise ValueError(f"unknown hypothesis: {update.hypothesis_id}")
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

    # -------------------------------------------------------------- auditing

    def record_violation(self, run_id: str, violation: HoldoutViolation) -> None:
        self.repository.append(run_id, EventType.VIOLATION_DETECTED, violation)

    def record_leaderboard_feedback(self, run_id: str, payload: dict[str, Any]) -> None:
        self.repository.append(run_id, EventType.LEADERBOARD_FEEDBACK_RECORDED, payload)


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


def _require_experiment(state: RunState, experiment_id: str) -> ExperimentProposal:
    proposal = state.proposals.get(experiment_id)
    if proposal is None:
        raise ValueError(f"unknown experiment: {experiment_id}")
    return proposal


def _artifact_refs(result: ExperimentResult) -> list[ArtifactRef]:
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


def _observation_from_result(result: ExperimentResult, artifact_root: str | Path | None) -> Observation:
    root = Path(artifact_root) if artifact_root is not None else None
    return Observation(
        id=f"OB-{uuid.uuid4().hex[:12]}",
        experiment_id=result.experiment_id,
        run_id=result.run_id,
        metrics=dict(result.metrics),
        code_commit_sha=result.commit_sha,
        environment_hash=result.environment_hash,
        dataset_fingerprint=result.dataset_fingerprint,
        artifacts=_artifact_refs(result),
        runtime=dict(result.runtime),
        exit_status=result.status,
        failure_class=result.failure_class,
        fold_metrics=_sidecar(root, SIDECAR_METRICS["fold_metrics"]),
        seed_metrics=_sidecar(root, SIDECAR_METRICS["seed_metrics"]),
        subgroup_metrics=_sidecar(root, SIDECAR_METRICS["subgroup_metrics"]),
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
