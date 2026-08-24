import pytest

from epistemic_loop.belief.evidence import EvidenceLevel
from epistemic_loop.belief.updater import belief_update, update_probability
from epistemic_loop.domain.enums import VerifierResult


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
