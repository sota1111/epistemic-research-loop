from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from epistemic_loop.benchmark.communication_ablation import CommunicationArmResult, evaluate_selective_sharing
from epistemic_loop.config import AppConfig, CompetitionConfig, RunConfig
from epistemic_loop.controller.belief_islands import BeliefAccessError, BeliefIslandStore
from epistemic_loop.controller.candidate_artifacts import CandidateArtifactValidator, candidate_required_outputs
from epistemic_loop.controller.diversity_control import CollectiveCollapseDetector, SemanticDuplicateDetector
from epistemic_loop.controller.evidence_vault import EvidenceVault, SelectiveEvidenceRouter
from epistemic_loop.controller.phase_gate import DiagnosticToCandidateGate
from epistemic_loop.controller.resource_scheduler import ResourceScheduler, ResourceUnavailable
from epistemic_loop.controller.token_efficiency import TokenBudgetLedger
from epistemic_loop.domain.enums import (
    CommunicationMode,
    EpistemicNiche,
    EvidenceVisibility,
    ExperimentKind,
    TerminalStatus,
)
from epistemic_loop.domain.models import (
    AgentBeliefState,
    CollapseMetrics,
    CommunicationPolicy,
    EvidenceObservation,
    EvidencePromotionRequest,
    EvidenceVerification,
    GlobalEvidence,
    LocalHypothesisBelief,
    ResourceEstimate,
    SemanticExperimentSignature,
)


def signature(*, operation: str = "adversarial_classifier", candidate: bool = False) -> SemanticExperimentSignature:
    return SemanticExperimentSignature(
        target_hypotheses=["temporal shift"],
        data_slice=["train vs test"],
        operation=[operation],
        observable=["auc"],
        decision_affected=["feature policy"],
        candidate_producing=candidate,
    )


def test_v2_config_defaults_are_local_selective_and_multi_candidate() -> None:
    config = AppConfig(
        run=RunConfig(),
        competition=CompetitionConfig(slug="ieee", metric_direction="maximize"),
    )
    assert config.agents.belief_scope == "local"
    assert config.agents.share_posteriors is False
    assert config.communication.broadcast_raw_results is False
    assert config.archive.minimum_candidate_slots == 8
    assert config.validation.horizons >= 3


def test_belief_islands_are_owner_only(tmp_path: Path) -> None:
    store = BeliefIslandStore(tmp_path / "beliefs")
    state = AgentBeliefState(
        agent_id="agent-a",
        epistemic_niche=EpistemicNiche.TEMPORAL,
        hypotheses=[
            LocalHypothesisBelief(
                id="A-H-001",
                claim="hidden test is later",
                prior_probability=0.55,
                posterior_probability=0.72,
            )
        ],
        validation_world_beliefs={"random": 0.1, "time": 0.6, "time_group": 0.3},
    )
    store.create(state)
    assert store.read("agent-a", requester="agent-a") == state
    with pytest.raises(BeliefAccessError):
        store.read("agent-a", requester="agent-b")


def test_evidence_is_stored_centrally_but_routed_selectively(tmp_path: Path) -> None:
    vault = EvidenceVault(tmp_path / "evidence")
    evidence = GlobalEvidence(
        evidence_id="EV-001",
        experiment_id="E-014",
        producer_agent="agent-a",
        observation=EvidenceObservation(metric="adversarial_auc", value=0.91, protocol="without_v"),
        verification=EvidenceVerification(
            artifact_contract_valid=True,
            independently_replicated=True,
            observation_interpretation_separated=True,
        ),
        visibility=EvidenceVisibility.PRIVATE,
        created_cycle=1,
    )
    vault.store(evidence)
    promoted = vault.promote(
        EvidencePromotionRequest(evidence_id="EV-001", expected_compute_saving=True, diversity_risk=0.2)
    )
    router = SelectiveEvidenceRouter(CommunicationPolicy(migration_interval_cycles=3))
    assert router.route(promoted, recipient_agent="agent-b", current_cycle=3) is None
    assert router.route(promoted, recipient_agent="agent-b", current_cycle=4) == promoted
    assert promoted.interpretation is None


def test_semantic_duplicate_ignores_ids_and_commands(proposal) -> None:
    first = proposal.model_copy(update={"id": "E-1", "semantic_signature": signature()})
    second = proposal.model_copy(
        update={
            "id": "E-2",
            "implementation_request": {"command": "python3 another.py"},
            "semantic_signature": signature(),
        }
    )
    assert SemanticDuplicateDetector().duplicates(second, [first]) == (first,)


def test_collective_collapse_requires_two_cycles() -> None:
    detector = CollectiveCollapseDetector()
    first = CollapseMetrics(
        dominant_cluster_fraction=0.8,
        experiment_family_effective_count=1.5,
        qd_niche_occupancy=2,
        hypothesis_family_budget_fraction=0.6,
        mean_agent_proposal_similarity=0.9,
        cycle=1,
    )
    second = first.model_copy(update={"cycle": 2})
    assert detector.assess(first).collapsed is False
    decision = detector.assess(second)
    assert decision.collapsed is True
    assert "reallocate_to_unexplored_niches" in decision.actions


def test_phase_gate_forces_candidate_after_three_valid_diagnostics(proposal) -> None:
    gate = DiagnosticToCandidateGate(max_consecutive_diagnostics=3)
    diagnostic = proposal.model_copy(update={"experiment_kind": ExperimentKind.DIAGNOSTIC})
    for _ in range(3):
        gate.record(diagnostic, TerminalStatus.COMPLETED)
    assert gate.evaluate(diagnostic).allowed is False
    candidate = proposal.model_copy(
        update={"experiment_kind": ExperimentKind.CANDIDATE_PRODUCING, "candidate_producing": True}
    )
    assert gate.evaluate(candidate).allowed is True
    gate.record(diagnostic, TerminalStatus.FAILED_RESOURCE)
    assert gate.consecutive_diagnostics(diagnostic.proposer_agent) == 3


def test_resource_scheduler_serializes_heavy_work(tmp_path: Path) -> None:
    scheduler = ResourceScheduler(
        total_memory_gb=32,
        total_cpu_cores=8,
        max_concurrent_heavy_experiments=1,
        memory_safety_margin=0.25,
        state_path=tmp_path / "scheduler.json",
    )
    heavy = ResourceEstimate(cpu_cores=4, memory_gb=16, expected_minutes=20, full_table_materialization=True)
    token = scheduler.reserve(heavy)
    with pytest.raises(ResourceUnavailable, match="memory|heavy"):
        scheduler.reserve(heavy)
    scheduler.release(token)
    assert scheduler.can_schedule(heavy).accepted


def _candidate_artifacts(root: Path) -> None:
    root.mkdir()
    (root / "model_artifact").mkdir()
    (root / "model_artifact" / "model.bin").write_bytes(b"model")
    candidate = {
        "candidate_id": "CAND-A-003",
        "source_agent": "agent-a",
        "git_commit": "abc123",
        "dataset_hash": "sha256:data",
        "environment_hash": "sha256:env",
        "validation": {
            "protocol": "multi_horizon_time_gap",
            "primary_score": 0.94,
            "fold_scores": [0.93, 0.94, 0.95],
            "score_std": 0.01,
        },
        "leakage_check": {"passed": True},
        "reproducibility": {"passed": True, "seeds": [42, 43, 44]},
    }
    (root / "candidate.yaml").write_text(yaml.safe_dump(candidate), encoding="utf-8")
    (root / "run_manifest.yaml").write_text(
        yaml.safe_dump({"candidate_id": "CAND-A-003", "dataset_hash": "sha256:data", "environment_hash": "sha256:env"}),
        encoding="utf-8",
    )
    (root / "feature_manifest.yaml").write_text(yaml.safe_dump({"features": ["uid_count"]}), encoding="utf-8")
    (root / "metrics.json").write_text(json.dumps({"auc": 0.94}), encoding="utf-8")
    for name in set(candidate_required_outputs()) - {
        "candidate.yaml",
        "run_manifest.yaml",
        "feature_manifest.yaml",
        "metrics.json",
        "model_artifact",
    }:
        (root / name).write_bytes(b"artifact")


def test_candidate_artifact_contract_rejects_exit_zero_style_partial_output(tmp_path: Path) -> None:
    root = tmp_path / "candidate"
    _candidate_artifacts(root)
    validator = CandidateArtifactValidator()
    assert validator.validate(root).valid
    (root / "oof_predictions.parquet").unlink()
    invalid = validator.validate(root)
    assert invalid.terminal_status == TerminalStatus.INVALID_ARTIFACT
    assert invalid.missing == ["oof_predictions.parquet"]


def test_token_budget_reserves_candidate_capacity_and_tracks_efficiency() -> None:
    ledger = TokenBudgetLedger(
        total_tokens=1000,
        proposal_token_limit=400,
        semantic_cluster_token_limit=600,
        candidate_reserve_fraction=0.4,
    )
    ledger.charge(signature(), tokens=300, candidate_producing=False, completed=True)
    with pytest.raises(ValueError, match="reserve"):
        ledger.authorize(signature(operation="feature_auc"), requested_tokens=350, candidate_producing=False)
    ledger.charge(
        signature(operation="candidate", candidate=True),
        tokens=400,
        candidate_producing=True,
        completed=True,
        valid_candidate=True,
    )
    assert ledger.metrics().tokens_per_valid_candidate == 700


def test_selective_communication_adoption_rule_is_independent_of_search_mode() -> None:
    decision = evaluate_selective_sharing(
        CommunicationArmResult(CommunicationMode.NO_SHARING, 0.93, 0.4, 0.8),
        CommunicationArmResult(CommunicationMode.SELECTIVE_DELAYED_ASYMMETRIC, 0.94, 0.2, 0.7),
        CommunicationArmResult(CommunicationMode.FULL_LIVE_SHARING, 0.95, 0.1, 0.6),
    )
    assert decision.selective_adopted
