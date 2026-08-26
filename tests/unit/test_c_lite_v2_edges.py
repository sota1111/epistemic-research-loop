from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from epistemic_loop.controller.belief_islands import BeliefIslandStore, GlobalControlPlane
from epistemic_loop.controller.candidate_artifacts import CandidateArtifactValidator, hash_snapshot
from epistemic_loop.controller.diversity_control import (
    MinimumNicheBudget,
    SemanticDuplicateDetector,
    effective_count,
    is_semantic_duplicate,
    semantic_similarity,
)
from epistemic_loop.controller.evidence_vault import EvidenceVault, SelectiveEvidenceRouter
from epistemic_loop.controller.resource_scheduler import ResourceScheduler, ResourceUnavailable
from epistemic_loop.controller.workspaces import AgentWorkspaceManager
from epistemic_loop.domain.enums import CommunicationMode, EpistemicNiche, EvidenceVisibility, ExperimentType
from epistemic_loop.domain.models import (
    AgentBeliefState,
    AgentNicheAssignment,
    CommunicationPolicy,
    EvidenceObservation,
    EvidencePromotionRequest,
    EvidenceVerification,
    GlobalControlState,
    GlobalEvidence,
    ResourceEstimate,
    SemanticExperimentSignature,
)


def sig(operation: str = "scan") -> SemanticExperimentSignature:
    return SemanticExperimentSignature(
        target_hypotheses=["shift"],
        data_slice=["train_test"],
        operation=[operation],
        observable=["auc"],
        decision_affected=["features"],
    )


def evidence(visibility: EvidenceVisibility, **changes: object) -> GlobalEvidence:
    return GlobalEvidence(
        evidence_id=str(changes.pop("evidence_id", "EV-1")),
        experiment_id="E-1",
        producer_agent="agent-a",
        observation=EvidenceObservation(metric="auc", value=0.8, protocol="forward"),
        verification=EvidenceVerification(),
        visibility=visibility,
        **changes,
    )


def test_belief_and_control_plane_edge_contracts(tmp_path: Path) -> None:
    beliefs = BeliefIslandStore(tmp_path / "beliefs")
    state = AgentBeliefState(agent_id="agent-a", epistemic_niche=EpistemicNiche.TEMPORAL)
    beliefs.create(state)
    with pytest.raises(ValueError, match="already exists"):
        beliefs.create(state)
    beliefs.update(state.model_copy(update={"experiment_history": ["E-1"]}), requester="agent-a")
    assert beliefs.agent_ids() == ("agent-a",)
    with pytest.raises(KeyError):
        beliefs.read("agent-b", requester="agent-b")
    with pytest.raises(ValueError):
        beliefs.read("../bad", requester="../bad")

    plane = GlobalControlPlane(tmp_path / "state" / "control.json")
    control = GlobalControlState(
        dataset_hash="sha256:data",
        active_agents=[AgentNicheAssignment(agent_id="agent-a", primary_niche=EpistemicNiche.TEMPORAL)],
    )
    plane.save(control)
    assert plane.load() == control
    with pytest.raises(FileNotFoundError):
        GlobalControlPlane(tmp_path / "missing.json").load()


def test_evidence_router_modes_visibility_and_vault_guards(tmp_path: Path) -> None:
    vault = EvidenceVault(tmp_path / "vault")
    private = evidence(EvidenceVisibility.PRIVATE)
    vault.store(private)
    assert vault.store(private).is_file()
    with pytest.raises(ValueError, match="immutable"):
        vault.store(
            private.model_copy(update={"observation": EvidenceObservation(metric="auc", value=0.9, protocol="x")})
        )
    with pytest.raises(KeyError):
        vault.get("missing")
    with pytest.raises(ValueError):
        vault.get("../bad")
    with pytest.raises(ValueError, match="cannot be promoted"):
        vault.promote(EvidencePromotionRequest(evidence_id="EV-1", expected_compute_saving=False, diversity_risk=0.8))

    selective = SelectiveEvidenceRouter()
    assert selective.route(private, recipient_agent="agent-a", current_cycle=0) == private
    assert selective.route(private, recipient_agent="controller", current_cycle=0, controller=True) == private
    assert selective.route(private, recipient_agent="agent-b", current_cycle=9) is None
    safety = evidence(EvidenceVisibility.GLOBAL_SAFETY, evidence_id="EV-safe")
    assert selective.route(safety, recipient_agent="agent-b", current_cycle=0) == safety
    challenge = evidence(
        EvidenceVisibility.SHARED_CHALLENGE,
        evidence_id="EV-challenge",
        challenge_target_agent="agent-b",
    )
    assert selective.route(challenge, recipient_agent="agent-c", current_cycle=9) is None
    assert selective.route(challenge, recipient_agent="agent-b", current_cycle=0).producer_agent == "withheld"  # type: ignore[union-attr]

    no_share = SelectiveEvidenceRouter(CommunicationPolicy(mode=CommunicationMode.NO_SHARING))
    assert no_share.route(safety, recipient_agent="agent-b", current_cycle=0) == safety
    assert no_share.route(private, recipient_agent="agent-b", current_cycle=0) is None
    full = SelectiveEvidenceRouter(CommunicationPolicy(mode=CommunicationMode.FULL_LIVE_SHARING))
    assert full.route(private, recipient_agent="agent-b", current_cycle=0) == private


def test_semantic_clustering_replication_and_minimum_niche_budget(proposal) -> None:
    first = proposal.model_copy(update={"id": "E-1", "semantic_signature": sig()})
    near = proposal.model_copy(update={"id": "E-2", "semantic_signature": sig()})
    other = proposal.model_copy(update={"id": "E-3", "semantic_signature": sig("aggregate")})
    assert semantic_similarity(sig(), sig()) == 1
    assert is_semantic_duplicate(first, near)
    replicated = near.model_copy(
        update={
            "experiment_type": ExperimentType.REPLICATION,
            "is_replication_of": "E-1",
            "replication": {
                "original_experiment_id": "E-1",
                "changed_condition": ["seed"],
                "replication_hypothesis": "same result under another seed",
            },
        }
    )
    assert not is_semantic_duplicate(first, replicated)
    detector = SemanticDuplicateDetector(similarity_threshold=0.8)
    assert detector.clusters([first, near, other])
    assert effective_count(["a", "a", "b"]) > 1
    assert effective_count([]) == 0
    with pytest.raises(ValueError):
        SemanticDuplicateDetector(similarity_threshold=2)

    budget = MinimumNicheBudget({"temporal": 0.5, "entity": 0.5}, 10)
    assert budget.protected("temporal")
    budget.charge("temporal", 5)
    assert not budget.protected("temporal")
    with pytest.raises(ValueError):
        budget.charge("missing", 1)
    with pytest.raises(KeyError):
        budget.protected("missing")


def test_resource_scheduler_all_admission_dimensions(tmp_path: Path) -> None:
    scheduler = ResourceScheduler(
        total_memory_gb=20,
        total_gpu_memory_gb=8,
        total_cpu_cores=4,
        max_concurrent_heavy_experiments=1,
        max_concurrent_light_experiments=1,
        max_concurrent_parquet_full_scans=1,
        memory_safety_margin=0.2,
    )
    light = ResourceEstimate(cpu_cores=1, memory_gb=2, expected_minutes=1)
    token = scheduler.reserve(light)
    assert scheduler.pressure()["running"] == 1
    with pytest.raises(ResourceUnavailable, match="light"):
        scheduler.reserve(light)
    with pytest.raises(KeyError):
        scheduler.release("missing")
    scheduler.release(token)
    assert not scheduler.can_schedule(ResourceEstimate(cpu_cores=5, memory_gb=2, expected_minutes=1)).accepted
    assert not scheduler.can_schedule(ResourceEstimate(cpu_cores=1, memory_gb=17, expected_minutes=1)).accepted
    assert not scheduler.can_schedule(
        ResourceEstimate(cpu_cores=1, memory_gb=2, gpu_memory_gb=9, expected_minutes=1)
    ).accepted
    with scheduler.reservation(ResourceEstimate(cpu_cores=1, memory_gb=2, expected_minutes=1)):
        assert scheduler.pressure()["running"] == 1
    with pytest.raises(ValueError):
        ResourceScheduler(total_memory_gb=1, memory_safety_margin=1)


def test_snapshot_hash_and_candidate_parse_failures(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / "a.txt").write_text("a", encoding="utf-8")
    assert hash_snapshot([data]).startswith("sha256:")
    with pytest.raises(FileNotFoundError):
        hash_snapshot([tmp_path / "missing"])
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    for name in ("candidate.yaml", "run_manifest.yaml", "feature_manifest.yaml", "metrics.json"):
        (candidate / name).write_text("[not, an, object]", encoding="utf-8")
    validation = CandidateArtifactValidator().validate(candidate)
    assert not validation.valid
    assert any("must contain an object" in item for item in validation.invalid)


def test_agent_workspace_manager_creates_generic_isolated_worktree(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    subprocess.run(["git", "init", str(repository)], check=True, capture_output=True)
    (repository / "README.md").write_text("initial\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repository), "add", "README.md"], check=True)
    environment = {
        **os.environ,
        "GIT_AUTHOR_NAME": "test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }
    subprocess.run(
        ["git", "-C", str(repository), "commit", "-m", "initial"],
        check=True,
        env=environment,
        capture_output=True,
    )
    manager = AgentWorkspaceManager(repository, tmp_path / "workspaces")
    path = manager.create("agent-01", base_ref="HEAD")
    assert manager.resolve("agent-01", requester="agent-01") == path
    with pytest.raises(PermissionError):
        manager.resolve("agent-01", requester="agent-02")
    with pytest.raises(ValueError):
        manager.create("temporal-solution", base_ref="HEAD")
    with pytest.raises(FileExistsError):
        manager.create("agent-01", base_ref="HEAD")
