from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from epistemic_loop.domain.enums import (  # noqa: E402
    Consequence,
    Direction,
    ExperimentType,
    HypothesisType,
)
from epistemic_loop.domain.models import (  # noqa: E402
    CostEstimate,
    EpistemicAssessment,
    ExperimentProposal,
    Hypothesis,
    PredictedOutcome,
    RobustnessAssessment,
    ScoreEstimate,
)


@pytest.fixture
def prediction() -> PredictedOutcome:
    return PredictedOutcome(
        description="temporal CV score is lower than random CV",
        metric_name="auc_gap",
        expected_direction=Direction.INCREASE,
        expected_range={"min": 0.02, "max": 0.20},
        condition="same features and model",
        discriminates_from=["H-GROUP"],
    )


@pytest.fixture
def hypothesis(prediction: PredictedOutcome) -> Hypothesis:
    false_prediction = prediction.model_copy(
        update={"description": "temporal and random CV are equivalent", "expected_direction": Direction.UNCHANGED}
    )
    return Hypothesis(
        id="H-001",
        run_id="run-001",
        type=HypothesisType.TEMPORAL_STRUCTURE,
        claim="time shift makes random CV optimistic",
        rationale="a time column is present",
        scope="validation",
        prior_confidence=0.5,
        current_confidence=0.5,
        predictions_if_true=[prediction],
        predictions_if_false=[false_prediction],
        falsification_requirements=["random vs temporal split"],
        downstream_consequence=Consequence.CRITICAL,
        created_by="test",
        prompt_version="v1",
    )


@pytest.fixture
def proposal(prediction: PredictedOutcome) -> ExperimentProposal:
    return ExperimentProposal(
        id="EXP-001",
        run_id="run-001",
        experiment_type=ExperimentType.DIAGNOSTIC,
        hypothesis_ids=["H-001"],
        research_question="Does temporal CV expose shift?",
        protocol="Run the same baseline on random and out-of-time splits",
        controls=["same features", "same model"],
        split_strategy="random_vs_temporal",
        seeds=[11, 23],
        metrics=["auc_gap"],
        predicted_outcomes=[prediction],
        decision_rule="support H-001 when temporal gap >= 0.02 in both seeds",
        expected_score_gain=ScoreEstimate(mean_gain=0.05, uncertainty=0.01),
        epistemic_assessment=EpistemicAssessment(
            hypothesis_discrimination=4,
            uncertainty_reduction=4,
            decision_consequence=4,
            search_space_reduction=3,
            outcome_observability=4,
            rationale="direct split comparison",
        ),
        robustness_assessment=RobustnessAssessment(
            seed_coverage=1,
            fold_coverage=1,
            subgroup_coverage=0.5,
            temporal_coverage=1,
            leakage_checks=0.5,
            rationale="two seeds and both split types",
        ),
        novelty_score=0.9,
        estimated_cost=CostEstimate(cpu_hours=1, wall_hours=0.5),
        implementation_request={"command": "python3 solver.py"},
        required_artifacts=["metrics.json", "fold_metrics.json"],
        lineage="validation",
    )


@pytest.fixture
def clone_proposal():
    def clone(value: ExperimentProposal, **changes: object) -> ExperimentProposal:
        payload = copy.deepcopy(value.model_dump())
        payload.update(changes)
        return ExperimentProposal.model_validate(payload)

    return clone
