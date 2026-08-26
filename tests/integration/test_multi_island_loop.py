from __future__ import annotations

from pathlib import Path

from epistemic_loop.controller.multi_island_loop import MultiIslandResearchLoop
from epistemic_loop.controller.resource_scheduler import ResourceScheduler
from epistemic_loop.domain.enums import EpistemicNiche, TerminalStatus
from epistemic_loop.domain.models import (
    AgentBeliefState,
    AgentNicheAssignment,
    ExperimentResult,
    ResourceEstimate,
    SemanticExperimentSignature,
)


def test_multi_island_loop_keeps_belief_private_and_artifacts_global(tmp_path: Path, proposal) -> None:
    loop = MultiIslandResearchLoop(
        tmp_path / "loop",
        dataset_hash="sha256:data",
        agents=[
            AgentNicheAssignment(agent_id="agent-a", primary_niche=EpistemicNiche.TEMPORAL),
            AgentNicheAssignment(agent_id="agent-b", primary_niche=EpistemicNiche.ENTITY_CLIENT),
        ],
        scheduler=ResourceScheduler(
            total_memory_gb=16,
            total_cpu_cores=4,
            memory_safety_margin=0.25,
            state_path=tmp_path / "scheduler.json",
        ),
    )
    loop.create_belief_island(AgentBeliefState(agent_id="agent-a", epistemic_niche=EpistemicNiche.TEMPORAL))
    experiment = proposal.model_copy(
        update={
            "id": "E-A-001",
            "proposer_agent": "agent-a",
            "epistemic_niche": EpistemicNiche.TEMPORAL,
            "semantic_signature": SemanticExperimentSignature(
                target_hypotheses=["temporal_shift"],
                data_slice=["forward_folds"],
                operation=["time_split"],
                observable=["fraud_auc"],
                decision_affected=["validation_policy"],
            ),
            "resource_estimate": ResourceEstimate(cpu_cores=1, memory_gb=2, expected_minutes=1),
        }
    )
    loop.propose(experiment, requester="agent-a")
    loop.start(experiment.id)
    result = ExperimentResult(
        experiment_id=experiment.id,
        run_id=experiment.run_id,
        attempt=1,
        status="failed",
        terminal_status=TerminalStatus.FAILED_RESOURCE,
        exit_code=137,
        commit_sha="abc",
        environment_hash="env",
        dataset_fingerprint="sha256:data",
    )
    loop.complete(result)

    assert len(loop.evidence.all()) == 1
    assert loop.phase_gate.consecutive_diagnostics("agent-a") == 0
    assert loop.control.load().running_experiments == []
    assert loop.beliefs.read("agent-a", requester="agent-a").experiment_history == [experiment.id]
