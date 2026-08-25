import pytest

from epistemic_loop.belief.evidence import EvidenceLevel
from epistemic_loop.belief.updater import bayesian_belief_update, belief_update, update_probability
from epistemic_loop.domain.enums import VerifierResult
from epistemic_loop.domain.models import OutcomeLikelihood


def test_log_odds_evidence_updates_and_clips() -> None:
    assert update_probability(0.5, 1.0) == pytest.approx(0.7310585)
    assert update_probability(0.95, 2.0) == 0.95
    assert update_probability(0.05, -2.0) == 0.05


def test_failed_verifier_does_not_move_belief() -> None:
    update = belief_update(
        "H-001",
        0.5,
        EvidenceLevel.STRONG_SUPPORT,
        "metric matched but verifier failed",
        ["OBS-001"],
        VerifierResult.FAIL,
    )
    assert update.posterior_confidence == 0.5
    assert update.evidence_strength == 0


def test_preregistered_likelihood_updates_belief_with_bayes_rule() -> None:
    likelihood = OutcomeLikelihood(label="rank_reversal", probability_if_true=0.8, probability_if_false=0.2)
    update = bayesian_belief_update(
        "H-001",
        0.5,
        likelihood,
        "rank reversal observed",
        ["OBS-001"],
        VerifierResult.PASS,
    )
    assert update.posterior_confidence == pytest.approx(0.8)
    assert update.update_method == "bayesian_likelihood"

    failed = bayesian_belief_update(
        "H-001",
        0.5,
        likelihood,
        "invalid measurement",
        ["OBS-001"],
        VerifierResult.FAIL,
    )
    assert failed.posterior_confidence == 0.5
