from __future__ import annotations

from dataclasses import dataclass

from epistemic_loop.domain.enums import ExperimentKind, ResearchPhase, TerminalStatus
from epistemic_loop.domain.models import ExperimentProposal


@dataclass(frozen=True)
class PhaseGateDecision:
    allowed: bool
    reason: str
    forced_phase: ResearchPhase | None = None


class DiagnosticToCandidateGate:
    """Bind diagnosis to a runnable candidate after the configured streak."""

    def __init__(self, *, max_consecutive_diagnostics: int = 3):
        if max_consecutive_diagnostics < 1:
            raise ValueError("max_consecutive_diagnostics must be positive")
        self.maximum = max_consecutive_diagnostics
        self._streak: dict[str, int] = {}

    def evaluate(self, proposal: ExperimentProposal) -> PhaseGateDecision:
        streak = self._streak.get(proposal.proposer_agent, 0)
        if streak < self.maximum or proposal.candidate_producing:
            return PhaseGateDecision(True, "phase gate satisfied")
        if proposal.candidate_exception_reason is not None:
            return PhaseGateDecision(
                True,
                f"candidate implementation deferred: {proposal.candidate_exception_reason}",
                ResearchPhase.PHASE_2_HYPOTHESIS_DISCRIMINATION,
            )
        return PhaseGateDecision(
            False,
            f"{self.maximum} consecutive diagnostics require a candidate-producing experiment",
            ResearchPhase.PHASE_3_CANDIDATE_IMPLEMENTATION,
        )

    def record(self, proposal: ExperimentProposal, terminal_status: TerminalStatus) -> None:
        # Resource and artifact failures are not observations and do not advance
        # the epistemic phase counter.
        if terminal_status != TerminalStatus.COMPLETED:
            return
        if proposal.candidate_producing or proposal.experiment_kind == ExperimentKind.CANDIDATE_PRODUCING:
            self._streak[proposal.proposer_agent] = 0
        else:
            self._streak[proposal.proposer_agent] = self._streak.get(proposal.proposer_agent, 0) + 1

    def consecutive_diagnostics(self, agent_id: str) -> int:
        return self._streak.get(agent_id, 0)
