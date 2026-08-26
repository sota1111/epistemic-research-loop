from __future__ import annotations

from pathlib import Path

import pytest

from epistemic_loop.config import (
    AppConfig,
    CompetitionConfig,
    PhaseWeights,
    RunConfig,
    StructureDiscoveryConfig,
)
from epistemic_loop.controller.evidence_vault import EvidenceVault
from epistemic_loop.controller.falsification_critic import FalsificationTestCritic
from epistemic_loop.controller.multi_island_loop import MultiIslandResearchLoop
from epistemic_loop.controller.structure_maturation import (
    LATENT_ENTITY_DEBT_REQUIREMENTS,
    StructureAccessError,
    StructureMaturationController,
)
from epistemic_loop.domain.enums import (
    AgentResearchState,
    EvidenceVisibility,
    ExperimentKind,
    StructuralDimension,
    StructureClassification,
    StructureLifecycleState,
    TerminalStatus,
)
from epistemic_loop.domain.models import (
    AgentBeliefState,
    AgentNicheAssignment,
    CandidateArtifactRecord,
    CandidateArtifactValidation,
    CandidateDescriptors,
    EvidenceObservation,
    EvidencePromotionRequest,
    EvidenceVerification,
    ExperimentResult,
    GlobalEvidence,
    ResourceEstimate,
    StructuralAlternative,
    StructuralHypothesis,
    StructureTestPreregistration,
)
from epistemic_loop.scoring.selector import score_experiment


def _provisional(identifier: str = "A05-H-UID-001") -> StructuralHypothesis:
    return StructuralHypothesis(
        id=identifier,
        run_id="run-v03",
        owner_agent="agent-05",
        claim="a UID proxy represents a persistent behavioral client",
        structure_type="latent_entity_proxy",
        observation_refs=["EV-overlap"],
        affected_dimensions=[
            StructuralDimension.ROW_INDEPENDENCE,
            StructuralDimension.ENTITY_GROUPING,
            StructuralDimension.FEATURE_GENERATION,
            StructuralDimension.CANDIDATE_ROUTING,
            StructuralDimension.POST_PROCESSING,
        ],
        observable_predictions=["causal memory gain is larger for known clients"],
        falsification_conditions=["matched null equals or exceeds real UID gain"],
        discrimination_plan=["run M0 through M5 on identical forward folds"],
        decisions_affected=["aggregation", "routing", "post_processing"],
        lifecycle_state=StructureLifecycleState.PROVISIONAL_STRUCTURE,
    )


def _with_alternatives(hypothesis: StructuralHypothesis) -> StructuralHypothesis:
    alternatives = [
        StructuralAlternative(
            id="H_frequency",
            claim="frequency rather than identity explains the gain",
            observable_predictions=["M2 and M3 have equal score"],
            falsification_conditions=["M3 exceeds M2 under paired forward evaluation"],
            null_model=True,
        ),
        StructuralAlternative(
            id="H_linkage_noise",
            claim="arbitrary linkage gives the same memory gain",
            observable_predictions=["M3 and M4 have equal score"],
            falsification_conditions=["M3 exceeds M4 after linkage shuffle"],
            null_model=True,
        ),
    ]
    return StructuralHypothesis.model_validate(
        {
            **hypothesis.model_dump(),
            "alternatives": alternatives,
            "lifecycle_state": StructureLifecycleState.ALTERNATIVES_REGISTERED,
        }
    )


def _test_design(*, discriminating: bool = True) -> StructureTestPreregistration:
    return StructureTestPreregistration(
        test_id="TEST-UID-LINK",
        target_hypothesis_id="A05-H-UID-001",
        competing_hypothesis_ids=["H_frequency", "H_linkage_noise"],
        prediction_by_hypothesis={
            "A05-H-UID-001": "M3 exceeds M2 and M4",
            "H_frequency": "M3 exceeds M2 and M4" if not discriminating else "M3 equals M2",
            "H_linkage_noise": "M3 equals M4",
        },
        falsification_condition="paired lower confidence bound is not positive",
        confounders_preserved=["group_size", "time_density", "missingness"],
        decision_affected="adopt or reject client-memory routing",
        power_plan="20 matched-null repetitions, three horizons and paired bootstrap confidence interval",
        fold_safe=True,
        semantic_signature={
            "target_hypotheses": ["behavioral client proxy"],
            "data_slice": ["forward known new clients"],
            "operation": ["linkage shuffle"],
            "observable": ["paired auc gain"],
            "decision_affected": ["client routing"],
            "candidate_producing": False,
        },
        null_repetitions=20,
    )


def test_v03_defaults_to_generic_agents_without_fixed_structure_roles() -> None:
    config = AppConfig(
        run=RunConfig(),
        competition=CompetitionConfig(slug="ieee", metric_direction="maximize"),
    )
    assert config.agents.niches == []
    assert config.agents.dynamic_structure_discovery is True
    assert config.agents.fixed_structure_roles is False
    assert config.diversity.minimum_niche_budget_enabled is False


def test_structure_controller_uses_configured_contract_thresholds(tmp_path: Path) -> None:
    config = StructureDiscoveryConfig(
        minimum_affected_dimensions=3,
        maturation_leverage_threshold=4,
        maturation_budget_fraction=0.2,
        matched_null_repetitions=25,
    )
    loop = MultiIslandResearchLoop(
        tmp_path,
        dataset_hash="sha256:data",
        agents=[AgentNicheAssignment(agent_id="agent-05")],
        structure_config=config,
    )
    assert loop.structures.minimum_affected_dimensions == 3
    assert loop.structures.leverage_threshold == 4
    assert loop.structures.default_fork_budget_fraction == 0.2
    assert loop.structures.critic.minimum_matched_null_repetitions == 25


def test_structural_contract_requires_two_dimensions_and_executable_implications() -> None:
    payload = _provisional().model_dump()
    payload["affected_dimensions"] = [StructuralDimension.ENTITY_GROUPING]
    with pytest.raises(ValueError, match="at least two"):
        StructuralHypothesis.model_validate(payload)
    payload = _provisional().model_dump()
    payload["observable_predictions"] = []
    with pytest.raises(ValueError, match="incomplete"):
        StructuralHypothesis.model_validate(payload)


def test_dynamic_maturation_fork_is_created_only_after_agent_discovery(tmp_path: Path) -> None:
    loop = MultiIslandResearchLoop(
        tmp_path,
        dataset_hash="sha256:data",
        agents=[AgentNicheAssignment(agent_id="agent-05")],
    )
    loop.create_belief_island(AgentBeliefState(agent_id="agent-05"))
    provisional = _provisional()
    loop.register_structural_hypothesis(provisional, requester="agent-05")
    belief = loop.beliefs.read("agent-05", requester="agent-05")
    assert belief.research_state == AgentResearchState.STRUCTURE_DISCOVERY
    alternatives = loop.advance_structural_hypothesis(_with_alternatives(provisional), requester="agent-05")
    fork = loop.create_structure_maturation_fork(
        alternatives.id,
        checkpoint_ref="git:agent-05@abc123",
        requester="agent-05",
    )
    assert {child.role.value for child in fork.children} == {"implementation", "null_skeptic", "verification"}
    assert loop.beliefs.read("agent-05", requester="agent-05").research_state == (
        AgentResearchState.STRUCTURE_MATURATION
    )
    loop.dissolve_structure_maturation_fork(fork.fork_id, requester="agent-05")
    assert loop.beliefs.read("agent-05", requester="agent-05").research_state == AgentResearchState.GENERIC_RESEARCH


def test_stateless_critic_rejects_a_test_that_does_not_separate_the_main_claim() -> None:
    result = FalsificationTestCritic().review(_test_design(discriminating=False))
    assert result.passed is False
    assert "main_false_cannot_pass" in result.reasons


def test_lifecycle_critic_debt_and_open_debt_promotion_block(tmp_path: Path) -> None:
    controller = StructureMaturationController(tmp_path / "structures")
    provisional = _provisional()
    controller.register(provisional, requester="agent-05")
    with pytest.raises(StructureAccessError):
        controller.get(provisional.id, requester="agent-other")
    controller.advance(_with_alternatives(provisional), requester="agent-05")
    critic = controller.preregister_test(provisional.id, _test_design(), requester="agent-05")
    assert critic.passed
    debt = controller.open_debt(provisional.id, candidate_id="CAND-05-001", requester="agent-05")
    assert tuple(debt.unresolved_requirements) == LATENT_ENTITY_DEBT_REQUIREMENTS
    assert controller.can_share_as_confirmed_fact(provisional.id) is False

    vault = EvidenceVault(tmp_path / "evidence")
    evidence = GlobalEvidence(
        evidence_id="EV-UID-GAIN",
        experiment_id="EXP-UID",
        producer_agent="agent-05",
        observation=EvidenceObservation(metric="forward_auc", value=0.94, protocol="M3_UID_MEMORY"),
        verification=EvidenceVerification(
            artifact_contract_valid=True,
            independently_replicated=True,
            observation_interpretation_separated=True,
        ),
        visibility=EvidenceVisibility.CONTROLLER_ONLY,
        structural_hypothesis_id=provisional.id,
        structure_validation_debt_open=True,
    )
    vault.store(evidence)
    with pytest.raises(ValueError, match="validation debt"):
        vault.promote(
            EvidencePromotionRequest(
                evidence_id=evidence.evidence_id,
                expected_compute_saving=True,
                diversity_risk=0.1,
            )
        )


def test_open_debt_forces_useful_encoding_classification(tmp_path: Path) -> None:
    controller = StructureMaturationController(tmp_path / "structures")
    provisional = _provisional()
    controller.register(provisional, requester="agent-05")
    controller.advance(_with_alternatives(provisional), requester="agent-05")
    controller.preregister_test(provisional.id, _test_design(), requester="agent-05")
    controller.record_partial_evidence(provisional.id, ["EV-M3"], requester="agent-05")
    controller.open_debt(provisional.id, candidate_id="CAND-05-001", requester="agent-05")
    assessment = controller.assess_promotion(
        provisional.id,
        structural_validity_passed=True,
        predictive_improvement_passed=True,
        evidence_refs=["EV-M3"],
        requester="agent-05",
    )
    assert assessment.classification == StructureClassification.USEFUL_ENCODING_UNVALIDATED_STRUCTURE
    assert assessment.structural_validity_passed is False


def test_inconclusive_structure_is_not_misclassified_as_rejected(tmp_path: Path) -> None:
    controller = StructureMaturationController(tmp_path / "structures")
    provisional = _provisional()
    controller.register(provisional, requester="agent-05")
    controller.advance(_with_alternatives(provisional), requester="agent-05")
    controller.preregister_test(provisional.id, _test_design(), requester="agent-05")
    controller.record_partial_evidence(provisional.id, ["EV-LOW-POWER"], requester="agent-05")
    assessment = controller.assess_promotion(
        provisional.id,
        structural_validity_passed=False,
        predictive_improvement_passed=False,
        evidence_refs=["EV-LOW-POWER"],
        requester="agent-05",
        conclusive=False,
    )
    assert assessment.lifecycle_state == StructureLifecycleState.INCONCLUSIVE
    assert assessment.classification is None
    assert controller.all_assessments() == (assessment,)


def test_candidate_use_automatically_opens_validation_debt(tmp_path: Path, proposal) -> None:
    loop = MultiIslandResearchLoop(
        tmp_path / "loop",
        dataset_hash="sha256:data",
        agents=[AgentNicheAssignment(agent_id="agent-05")],
    )
    loop.create_belief_island(AgentBeliefState(agent_id="agent-05"))
    hypothesis = _provisional()
    loop.register_structural_hypothesis(hypothesis, requester="agent-05")

    class PassingValidator:
        def validate(self, root: str) -> CandidateArtifactValidation:
            return CandidateArtifactValidation(valid=True, terminal_status=TerminalStatus.COMPLETED)

    loop.archive.validator = PassingValidator()  # type: ignore[assignment]
    experiment = proposal.model_copy(
        update={
            "id": "EXP-UID-CAND",
            "proposer_agent": "agent-05",
            "experiment_kind": ExperimentKind.CANDIDATE_PRODUCING,
            "candidate_producing": True,
            "structural_hypothesis_id": hypothesis.id,
            "resource_estimate": ResourceEstimate(memory_gb=1, expected_minutes=1),
        }
    )
    loop.propose(experiment, requester="agent-05")
    loop.start(experiment.id)
    candidate = CandidateArtifactRecord(
        candidate_id="CAND-05-001",
        source_agent="agent-05",
        git_commit="abc123",
        dataset_hash="sha256:data",
        environment_hash="sha256:env",
        artifact_root=str(tmp_path / "candidate"),
        descriptor=CandidateDescriptors(source_agent="agent-05"),
        primary_score=0.94,
        leakage_check_passed=True,
        reproducibility_passed=True,
        structural_hypothesis_ids=[hypothesis.id],
    )
    loop.complete(
        ExperimentResult(
            experiment_id=experiment.id,
            run_id=experiment.run_id,
            attempt=1,
            status="completed",
            commit_sha="abc123",
            environment_hash="sha256:env",
            dataset_fingerprint="sha256:data",
            metrics={"forward_auc": 0.94},
        ),
        candidate=candidate,
    )
    debt = loop.structures.debt(hypothesis.id, requester="agent-05")
    assert debt.affects_candidates == [candidate.candidate_id]
    assert loop.control.load().open_validation_debts == [debt.debt_id]
    stored_evidence = loop.evidence.all()[0]
    assert stored_evidence.structure_validation_debt_open


def test_resolved_debt_allows_validated_actionable_structure(tmp_path: Path) -> None:
    controller = StructureMaturationController(tmp_path / "structures")
    provisional = _provisional("A05-H-UID-VALID")
    controller.register(provisional, requester="agent-05")
    alternatives = _with_alternatives(provisional)
    alternatives = StructuralHypothesis.model_validate(
        {
            **alternatives.model_dump(),
            "alternatives": [item.model_copy(update={"id": item.id + "-VALID"}) for item in alternatives.alternatives],
        }
    )
    controller.advance(alternatives, requester="agent-05")
    design = _test_design().model_copy(
        update={
            "test_id": "TEST-UID-VALID",
            "target_hypothesis_id": provisional.id,
            "competing_hypothesis_ids": [item.id for item in alternatives.alternatives],
            "prediction_by_hypothesis": {
                provisional.id: "real linkage wins",
                alternatives.alternatives[0].id: "frequency only ties",
                alternatives.alternatives[1].id: "shuffle ties",
            },
        }
    )
    controller.preregister_test(provisional.id, design, requester="agent-05")
    controller.record_partial_evidence(provisional.id, ["EV-G1-G9"], requester="agent-05")
    controller.open_debt(provisional.id, candidate_id="CAND-VALID", requester="agent-05")
    for requirement in LATENT_ENTITY_DEBT_REQUIREMENTS:
        controller.resolve_requirement(
            provisional.id,
            requirement,
            artifact_ref=f"artifact:{requirement}",
            requester="agent-05",
        )
    assessment = controller.assess_promotion(
        provisional.id,
        structural_validity_passed=True,
        predictive_improvement_passed=True,
        evidence_refs=["EV-G1-G9"],
        requester="agent-05",
    )
    assert assessment.classification == StructureClassification.VALIDATED_ACTIONABLE_STRUCTURE
    assert controller.can_share_as_confirmed_fact(provisional.id)


def test_utility_rewards_robust_discrimination_and_debt_reduction(proposal) -> None:
    structural = proposal.model_copy(
        update={
            "structural_hypothesis_id": "A05-H-UID-001",
            "structure_test_id": "TEST-UID-LINK",
            "structural_leverage": 5.0,
            "discrimination_value": 0.8,
            "discrimination_values_by_prior": [0.6, 0.3],
            "validation_debt_reduction": 0.6,
        }
    )
    weights = PhaseWeights(
        pragmatic=0,
        epistemic=0,
        robustness=0,
        diversity=0,
        structural_leverage=1,
        discrimination=1,
        validation_debt_reduction=1,
    )
    utility = score_experiment(structural, weights, cost_lambda=0, risk_lambda=0)
    assert utility.structural_leverage == 0.5
    assert utility.discrimination == 0.3
    assert utility.validation_debt_reduction == 0.6
    assert utility.total == pytest.approx(1.4)


def test_structural_utility_cannot_be_claimed_without_registry_and_critic_binding(proposal) -> None:
    payload = proposal.model_dump()
    payload["structural_leverage"] = 10
    with pytest.raises(ValueError, match="registered structural hypothesis"):
        type(proposal).model_validate(payload)
    payload = proposal.model_dump()
    payload.update(
        {
            "structural_hypothesis_id": "A05-H-UID-001",
            "discrimination_value": 1,
        }
    )
    with pytest.raises(ValueError, match="preregistered structure test"):
        type(proposal).model_validate(payload)
