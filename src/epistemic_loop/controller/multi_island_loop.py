from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from epistemic_loop.adapters.executor.base import ExecutorAdapter
from epistemic_loop.config import StructureDiscoveryConfig
from epistemic_loop.controller.belief_islands import BeliefIslandStore, GlobalControlPlane
from epistemic_loop.controller.diversity_control import (
    CollapseDecision,
    CollectiveCollapseDetector,
    SemanticDuplicateDetector,
)
from epistemic_loop.controller.evidence_vault import EvidenceVault, SelectiveEvidenceRouter
from epistemic_loop.controller.falsification_critic import FalsificationTestCritic
from epistemic_loop.controller.phase_gate import DiagnosticToCandidateGate
from epistemic_loop.controller.resource_scheduler import ResourceScheduler
from epistemic_loop.controller.structure_maturation import StructureMaturationController
from epistemic_loop.domain.enums import AgentResearchState, StructureLifecycleState, TerminalStatus
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
    FalsificationCriticResult,
    GlobalControlState,
    GlobalEvidence,
    RemainingBudget,
    StructuralHypothesis,
    StructureMaturationFork,
    StructurePromotionAssessment,
    StructureTestPreregistration,
    StructureValidationDebt,
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
        structure_config: StructureDiscoveryConfig | None = None,
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
        structure_settings = structure_config or StructureDiscoveryConfig()
        self.structures = StructureMaturationController(
            self.root / "structures",
            minimum_affected_dimensions=structure_settings.minimum_affected_dimensions,
            leverage_threshold=structure_settings.maturation_leverage_threshold,
            default_fork_budget_fraction=structure_settings.maturation_budget_fraction,
            critic=FalsificationTestCritic(
                minimum_matched_null_repetitions=structure_settings.matched_null_repetitions
            ),
            debt_requirements_by_type={"latent_entity_proxy": structure_settings.latent_entity_debt_requirements},
        )
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
        if assignment.primary_niche is not None and state.epistemic_niche != assignment.primary_niche:
            raise ValueError("belief island niche must match its control-plane assignment")
        if assignment.primary_niche is None and state.research_state != AgentResearchState.GENERIC_RESEARCH:
            raise ValueError("a new generic agent must begin in generic_research state")
        self.beliefs.create(state)

    def propose(self, proposal: ExperimentProposal, *, requester: str) -> None:
        if proposal.proposer_agent != requester:
            raise PermissionError("an agent may submit only its own proposal")
        assignment = self._assignment(requester)
        allowed_niches = {assignment.primary_niche, assignment.secondary_niche} - {None}
        if allowed_niches and proposal.epistemic_niche not in allowed_niches:
            raise ValueError("proposal is outside the agent's assigned epistemic niches")
        structure: StructuralHypothesis | None = None
        if proposal.structural_hypothesis_id is not None:
            structure = self.structures.get(proposal.structural_hypothesis_id, requester=requester)
            if (
                proposal.structural_leverage
                and abs(proposal.structural_leverage - structure.structural_leverage) > 1e-9
            ):
                raise ValueError("proposal structural leverage must be derived from the registered hypothesis")
        if proposal.structure_test_id is not None and (
            structure is None
            or proposal.structure_test_id not in {item.test_id for item in structure.preregistered_tests}
        ):
            raise ValueError("structure test must pass critic review and preregistration before proposal")
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
        structure_debt_open = False
        if proposal.structural_hypothesis_id:
            try:
                structure_debt_open = bool(
                    self.structures.debt(proposal.structural_hypothesis_id, controller=True).remaining_requirements
                )
            except KeyError:
                structure_debt_open = candidate is not None
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
                structural_hypothesis_id=proposal.structural_hypothesis_id,
                structure_validation_debt_open=structure_debt_open,
            )
        if evidence.experiment_id != result.experiment_id or evidence.producer_agent != proposal.proposer_agent:
            raise ValueError("evidence identity does not match its producer proposal")
        if proposal.structural_hypothesis_id:
            evidence = evidence.model_copy(
                update={
                    "structural_hypothesis_id": proposal.structural_hypothesis_id,
                    "structure_validation_debt_open": structure_debt_open,
                }
            )
        self.evidence.store(evidence)
        self.phase_gate.record(proposal, result.terminal_status)
        if candidate is not None:
            if not proposal.candidate_producing or result.terminal_status != TerminalStatus.COMPLETED:
                raise ValueError("only a completed candidate-producing experiment can promote a candidate")
            if candidate.source_agent != proposal.proposer_agent:
                raise ValueError("candidate source agent does not match the proposal")
            if (
                proposal.structural_hypothesis_id
                and proposal.structural_hypothesis_id not in candidate.structural_hypothesis_ids
            ):
                raise ValueError("a structure-derived candidate must declare the structural hypothesis it uses")
            for hypothesis_id in candidate.structural_hypothesis_ids:
                structure = self.structures.get(hypothesis_id, requester=proposal.proposer_agent)
                if structure.owner_agent != proposal.proposer_agent:
                    raise PermissionError("candidate may use only its owner's agent-local structural hypothesis")
            debt_ids = [f"DEBT-{item}" for item in candidate.structural_hypothesis_ids]
            candidate = candidate.model_copy(update={"open_structure_validation_debt_ids": debt_ids})
            self.archive.promote(candidate)
            for hypothesis_id in candidate.structural_hypothesis_ids:
                self.structures.open_debt(
                    hypothesis_id,
                    candidate_id=candidate.candidate_id,
                    requester=proposal.proposer_agent,
                )
            self._sync_structure_control_state()
        self._update_owner_history(proposal, candidate)

    def register_structural_hypothesis(self, hypothesis: StructuralHypothesis, *, requester: str) -> None:
        self._assignment(requester)
        if hypothesis.owner_agent != requester:
            raise PermissionError("an agent may register only its own structural hypothesis")
        self.structures.register(hypothesis, requester=requester)
        self._update_agent_structure_state(
            requester,
            AgentResearchState.STRUCTURE_DISCOVERY,
            hypothesis_id=hypothesis.id,
        )

    def advance_structural_hypothesis(
        self,
        hypothesis: StructuralHypothesis,
        *,
        requester: str,
    ) -> StructuralHypothesis:
        return self.structures.advance(hypothesis, requester=requester)

    def preregister_structure_test(
        self,
        hypothesis_id: str,
        test: StructureTestPreregistration,
        *,
        requester: str,
    ) -> FalsificationCriticResult:
        return self.structures.preregister_test(hypothesis_id, test, requester=requester)

    def create_structure_maturation_fork(
        self,
        hypothesis_id: str,
        *,
        checkpoint_ref: str,
        requester: str,
        reserved_budget_fraction: float | None = None,
    ) -> StructureMaturationFork:
        fork = self.structures.create_fork(
            hypothesis_id,
            checkpoint_ref=checkpoint_ref,
            requester=requester,
            reserved_budget_fraction=reserved_budget_fraction,
        )
        self._update_agent_structure_state(requester, AgentResearchState.STRUCTURE_MATURATION)
        self._sync_structure_control_state()
        return fork

    def dissolve_structure_maturation_fork(self, fork_id: str, *, requester: str) -> StructureMaturationFork:
        fork = self.structures.dissolve_fork(fork_id, requester=requester)
        self._update_agent_structure_state(requester, AgentResearchState.GENERIC_RESEARCH)
        self._sync_structure_control_state()
        return fork

    def resolve_structure_validation_requirement(
        self,
        hypothesis_id: str,
        requirement: str,
        *,
        artifact_ref: str,
        requester: str,
    ) -> StructureValidationDebt:
        debt = self.structures.resolve_requirement(
            hypothesis_id,
            requirement,
            artifact_ref=artifact_ref,
            requester=requester,
        )
        self._sync_structure_control_state()
        return debt

    def assess_structural_hypothesis(
        self,
        hypothesis_id: str,
        *,
        structural_validity_passed: bool,
        predictive_improvement_passed: bool,
        evidence_refs: Sequence[str],
        requester: str,
        conclusive: bool = True,
    ) -> StructurePromotionAssessment:
        assessment = self.structures.assess_promotion(
            hypothesis_id,
            structural_validity_passed=structural_validity_passed,
            predictive_improvement_passed=predictive_improvement_passed,
            evidence_refs=evidence_refs,
            requester=requester,
            conclusive=conclusive,
        )
        if assessment.lifecycle_state in {
            StructureLifecycleState.VALIDATED_STRUCTURE,
            StructureLifecycleState.USEFUL_ENCODING_UNVALIDATED_STRUCTURE,
            StructureLifecycleState.STRUCTURALLY_PLAUSIBLE_NON_ACTIONABLE,
            StructureLifecycleState.FALSIFIED,
            StructureLifecycleState.INCONCLUSIVE,
        }:
            self._update_agent_structure_state(requester, AgentResearchState.GENERIC_RESEARCH)
        self._sync_structure_control_state()
        return assessment

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

    def _update_agent_structure_state(
        self,
        agent_id: str,
        research_state: AgentResearchState,
        *,
        hypothesis_id: str | None = None,
    ) -> None:
        try:
            belief = self.beliefs.read(agent_id, requester=agent_id)
        except KeyError:
            return
        refs = list(belief.structural_hypothesis_refs)
        if hypothesis_id is not None and hypothesis_id not in refs:
            refs.append(hypothesis_id)
        self.beliefs.update(
            belief.model_copy(
                update={
                    "research_state": research_state,
                    "structural_hypothesis_refs": refs,
                }
            ),
            requester=agent_id,
        )

    def _sync_structure_control_state(self) -> None:
        state = self.control.load()
        self.control.save(
            state.model_copy(
                update={
                    "active_structure_forks": list(self.structures.active_fork_ids()),
                    "open_validation_debts": list(self.structures.open_debt_ids()),
                }
            )
        )

    def _assignment(self, agent_id: str) -> AgentNicheAssignment:
        assignment = next((item for item in self.control.load().active_agents if item.agent_id == agent_id), None)
        if assignment is None:
            raise KeyError(f"unknown active agent: {agent_id}")
        return assignment
