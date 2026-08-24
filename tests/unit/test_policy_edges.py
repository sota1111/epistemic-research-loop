from pathlib import Path

import pytest

from epistemic_loop.belief.calibration import brier_score
from epistemic_loop.belief.deduplication import claim_similarity, find_merge_candidate
from epistemic_loop.config import PhaseWeights, load_config
from epistemic_loop.controller.phase_policy import PhaseEvidence, decide_phase
from epistemic_loop.controller.stop_policy import should_stop
from epistemic_loop.domain.enums import HypothesisStatus, Phase
from epistemic_loop.domain.models import Budget, BudgetUsage, Hypothesis
from epistemic_loop.scoring.normalization import higher_is_better, min_max


def test_calibration_and_deduplication(hypothesis: Hypothesis) -> None:
    assert brier_score([0.8, 0.2], [True, False]) == pytest.approx(0.04)
    with pytest.raises(ValueError):
        brier_score([], [])
    candidate = hypothesis.model_copy(update={"id": "H-NEW", "version": 2})
    assert claim_similarity(hypothesis.claim, candidate.claim) == 1
    assert find_merge_candidate(candidate, [hypothesis]) == hypothesis
    unrelated = candidate.model_copy(update={"claim": "candidate recall is limiting the ranker"})
    assert find_merge_candidate(unrelated, [hypothesis]) is None


def test_normalization_covers_metric_directions() -> None:
    assert higher_is_better(0.8, "maximize") == 0.8
    assert higher_is_better(0.8, "minimize") == -0.8
    with pytest.raises(ValueError):
        higher_is_better(0.8, "sideways")
    assert min_max([]) == []
    assert min_max([2, 2]) == [0.5, 0.5]
    assert min_max([1, 3]) == [0, 1]


def test_phase_policy_progresses_and_can_return_from_exploitation(hypothesis: Hypothesis) -> None:
    tested = [
        hypothesis.model_copy(
            update={
                "id": f"H-{index}",
                "version": 2,
                "status": HypothesisStatus.SUPPORTED,
                "current_confidence": 0.95,
            }
        )
        for index in range(3)
    ]
    assert (
        decide_phase(
            Phase.DISCOVERY,
            tested,
            PhaseEvidence(validation_locked=True, critical_leakage_resolved=True),
        )
        == Phase.CONSOLIDATION
    )
    assert (
        decide_phase(
            Phase.CONSOLIDATION,
            tested,
            PhaseEvidence(stable_lineages=1, ablations_complete=True, search_space_defined=True),
        )
        == Phase.EXPLOITATION
    )
    assert decide_phase(Phase.EXPLOITATION, tested, PhaseEvidence(anomaly_detected=True)) == Phase.CONSOLIDATION
    assert decide_phase(Phase.DISCOVERY, [], PhaseEvidence()) == Phase.DISCOVERY


def test_stop_policy_reports_all_blocking_conditions() -> None:
    budget = Budget(max_experiments=1, max_cpu_hours=1, max_gpu_hours=1)
    usage = BudgetUsage(experiments=1, cpu_hours=1, gpu_hours=1)
    decision = should_stop(
        budget,
        usage,
        maximum_candidate_utility=-1,
        minimum_utility=0,
        rounds_without_information=3,
        validation_stable=False,
        holdout_violation=True,
        rule_violation=True,
        human_stop=True,
    )
    assert decision.stop and decision.blocked
    assert len(decision.reasons) == 9
    assert not should_stop(Budget(), BudgetUsage(), maximum_candidate_utility=1, minimum_utility=0).stop


def test_config_env_expansion_and_phase_weights(tmp_path, monkeypatch) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "run: {mode: epistemic, seed: 1}\n"
        "competition: {slug: demo, metric_direction: maximize, data_path: '${DATA_FIXTURE}'}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DATA_FIXTURE", "/tmp/data")
    assert load_config(path).competition.data_path == "/tmp/data"
    monkeypatch.delenv("DATA_FIXTURE")
    with pytest.raises(ValueError, match="environment variable"):
        load_config(path)
    weights = PhaseWeights(pragmatic=1, epistemic=1, robustness=1, diversity=1)
    config = load_config(Path(__file__).resolve().parents[2] / "configs" / "defaults.yaml")
    config.selection.discovery = weights
    assert config.selection.for_phase(Phase.DISCOVERY) == weights
    assert config.selection.for_phase(Phase.CONSOLIDATION) == config.selection.consolidation
    assert config.selection.for_phase(Phase.EXPLOITATION) == config.selection.exploitation
