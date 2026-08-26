from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from epistemic_loop.adapters.executor.base import ExecutorAdapter
from epistemic_loop.controller.belief_islands import BeliefIslandStore, GlobalControlPlane
from epistemic_loop.controller.diversity_control import (
    CollapseDecision,
    CollectiveCollapseDetector,
    SemanticDuplicateDetector,
)
from epistemic_loop.controller.evidence_vault import EvidenceVault, SelectiveEvidenceRouter
from epistemic_loop.controller.phase_gate import DiagnosticToCandidateGate
from epistemic_loop.controller.resource_scheduler import ResourceScheduler
from epistemic_loop.domain.enums import TerminalStatus
from epistemic_loop.domain.models import (
    AgentBeliefState,
    AgentNicheAssignment,
    CandidateArtifactRecord,
    CollapseMetrics,
    CommunicationPolicy,
    EvidenceObservation,
    EvidenceVerification,
    ExperimentProposal,
    ExperimentRequest,
    ExperimentResult,
    GlobalControlState,
    GlobalEvidence,
    RemainingBudget,
)
from epistemic_loop.qd.candidate_archive import CandidateArchive


class MultiIslandResearchLoop:
    """v0.2 control plane joining private beliefs to shared execution artifacts."""

    def __init__(
        self,
        root: str | Path,
        *,
        dataset_hash: str,
        agents: Sequence[AgentNicheAssignment],
        remaining_budget: RemainingBudget | None = None,
        communication_policy: CommunicationPolicy | None = None,
        scheduler: ResourceScheduler | None = None,
    ):
        if len({item.agent_id for item in agents}) != len(agents):
            raise ValueError("agent identifiers must be unique")
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.beliefs = BeliefIslandStore(self.root / "beliefs")
        self.control = GlobalControlPlane(self.root / "global_control.json")
        self.evidence = EvidenceVault(self.root / "evidence")
        self.router = SelectiveEvidenceRouter(communication_policy)
        self.scheduler = scheduler or ResourceScheduler(state_path=self.root / "scheduler.json")
        self.archive = CandidateArchive()
        self.duplicates = SemanticDuplicateDetector()
        self.collapse = CollectiveCollapseDetector()
        self.phase_gate = DiagnosticToCandidateGate()
        self._proposals: dict[str, ExperimentProposal] = {}
        self._reservations: dict[str, str] = {}
        state = GlobalControlState(
            dataset_hash=dataset_hash,
            remaining_budget=remaining_budget or RemainingBudget(),
            active_agents=list(agents),
        )
        self.control.save(state)

    def create_belief_island(self, state: AgentBeliefState) -> None:
        assignment = self._assignment(state.agent_id)
        if state.epistemic_niche != assignment.primary_niche:
            raise ValueError("belief island niche must match its control-plane assignment")
        self.beliefs.create(state)

    def propose(self, proposal: ExperimentProposal, *, requester: str) -> None:
        if proposal.proposer_agent != requester:
            raise PermissionError("an agent may submit only its own proposal")
        assignment = self._assignment(requester)
        allowed_niches = {assignment.primary_niche, assignment.secondary_niche}
        if proposal.epistemic_niche not in allowed_niches:
            raise ValueError("proposal is outside the agent's assigned epistemic niches")
        gate = self.phase_gate.evaluate(proposal)
        if not gate.allowed:
            raise ValueError(gate.reason)
        duplicates = self.duplicates.duplicates(proposal, list(self._proposals.values()))
        if duplicates:
            raise ValueError("semantic duplicate proposal; use a preregistered replication")
        if proposal.resource_estimate is None:
            raise ValueError("multi-island proposals require a resource estimate")
        if proposal.id in self._proposals:
            raise ValueError(f"proposal identifier already exists: {proposal.id}")
        estimate = proposal.resource_estimate
        if (
            estimate.memory_gb > self.scheduler.usable_memory_gb
            or estimate.cpu_cores > self.scheduler.total_cpu_cores
            or estimate.gpu_memory_gb > self.scheduler.total_gpu_memory_gb
        ):
            raise ValueError("proposal exceeds static scheduler capacity")
        self._proposals[proposal.id] = proposal
        state = self.control.load()
        self.control.save(state.model_copy(update={"experiment_queue": [*state.experiment_queue, proposal.id]}))

    def start(self, experiment_id: str) -> None:
        proposal = self._proposals[experiment_id]
        state = self.control.load()
        if experiment_id in self._reservations or experiment_id not in state.experiment_queue:
            raise ValueError("experiment is not waiting in the queue")
        if proposal.resource_estimate is None:  # pragma: no cover - guaranteed by propose
            raise ValueError("resource estimate missing")
        token = self.scheduler.reserve(proposal.resource_estimate)
        self._reservations[experiment_id] = token
        queue = [item for item in state.experiment_queue if item != experiment_id]
        self.control.save(
            state.model_copy(
                update={
                    "experiment_queue": queue,
                    "running_experiments": [*state.running_experiments, experiment_id],
                    "resource_pressure": self.scheduler.pressure(),
                }
            )
        )

    def execute(self, request: ExperimentRequest, executor: ExecutorAdapter) -> ExperimentResult:
        self.start(request.experiment_id)
        try:
            result = executor.submit(request)
        except Exception:
            self._release(request.experiment_id)
            raise
        self.complete(result)
        return result

    def complete(
        self,
        result: ExperimentResult,
        *,
        evidence: GlobalEvidence | None = None,
        candidate: CandidateArtifactRecord | None = None,
    ) -> None:
        try:
            self._complete_result(result, evidence=evidence, candidate=candidate)
        finally:
            if result.experiment_id in self._reservations:
                self._release(result.experiment_id)

    def _complete_result(
        self,
        result: ExperimentResult,
        *,
        evidence: GlobalEvidence | None,
        candidate: CandidateArtifactRecord | None,
    ) -> None:
        proposal = self._proposals[result.experiment_id]
        if result.experiment_id not in self._reservations:
            raise ValueError("experiment was not started by this control plane")
        if result.run_id != proposal.run_id:
            raise ValueError("result run identity does not match the proposal")
        if result.status in {"queued", "running"}:
            raise ValueError("cannot complete an experiment with a non-terminal result")
        if result.terminal_status is None:  # pragma: no cover - result validator assigns it
            raise ValueError("terminal status missing")
        if evidence is None:
            metric, value = next(iter(result.metrics.items()), ("terminal_status", result.terminal_status.value))
            evidence = GlobalEvidence(
                evidence_id=f"EV-{result.run_id}-{result.experiment_id}-{result.attempt}",
                experiment_id=result.experiment_id,
                producer_agent=proposal.proposer_agent,
                observation=EvidenceObservation(metric=metric, value=value, protocol=proposal.protocol),
                artifacts={Path(item).name: item for item in result.artifact_refs},
                verification=EvidenceVerification(
                    artifact_contract_valid=result.terminal_status == TerminalStatus.COMPLETED,
                ),
            )
        if evidence.experiment_id != result.experiment_id or evidence.producer_agent != proposal.proposer_agent:
            raise ValueError("evidence identity does not match its producer proposal")
        self.evidence.store(evidence)
        self.phase_gate.record(proposal, result.terminal_status)
        if candidate is not None:
            if not proposal.candidate_producing or result.terminal_status != TerminalStatus.COMPLETED:
                raise ValueError("only a completed candidate-producing experiment can promote a candidate")
            if candidate.source_agent != proposal.proposer_agent:
                raise ValueError("candidate source agent does not match the proposal")
            self.archive.promote(candidate)
        self._update_owner_history(proposal, candidate)

    def routed_evidence(
        self,
        *,
        recipient_agent: str,
        current_cycle: int,
        phase_boundary: bool = False,
    ) -> tuple[GlobalEvidence, ...]:
        self._assignment(recipient_agent)
        return self.router.migration(
            list(self.evidence.all()),
            recipient_agent=recipient_agent,
            current_cycle=current_cycle,
            phase_boundary=phase_boundary,
        )

    def assess_collapse(self, metrics: CollapseMetrics) -> CollapseDecision:
        decision = self.collapse.assess(metrics)
        state = self.control.load()
        self.control.save(state.model_copy(update={"collapse_metrics": metrics.model_dump(mode="json")}))
        return decision

    def _update_owner_history(
        self,
        proposal: ExperimentProposal,
        candidate: CandidateArtifactRecord | None,
    ) -> None:
        owner = proposal.proposer_agent
        try:
            belief = self.beliefs.read(owner, requester=owner)
        except KeyError:
            return
        candidate_refs = list(belief.candidate_refs)
        if candidate is not None:
            candidate_refs.append(candidate.candidate_id)
        updated = belief.model_copy(
            update={
                "experiment_history": [*belief.experiment_history, proposal.id],
                "candidate_refs": candidate_refs,
            }
        )
        self.beliefs.update(updated, requester=owner)

    def _release(self, experiment_id: str) -> None:
        token = self._reservations.pop(experiment_id, None)
        if token is not None:
            self.scheduler.release(token)
        state = self.control.load()
        self.control.save(
            state.model_copy(
                update={
                    "running_experiments": [item for item in state.running_experiments if item != experiment_id],
                    "resource_pressure": self.scheduler.pressure(),
                    "archive_occupancy": self.archive.occupancy,
                }
            )
        )

    def _assignment(self, agent_id: str) -> AgentNicheAssignment:
        assignment = next((item for item in self.control.load().active_agents if item.agent_id == agent_id), None)
        if assignment is None:
            raise KeyError(f"unknown active agent: {agent_id}")
        return assignment
