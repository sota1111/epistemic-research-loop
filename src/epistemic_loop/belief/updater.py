from __future__ import annotations

import math
import uuid

from epistemic_loop.belief.evidence import EVIDENCE_WEIGHTS, EvidenceLevel
from epistemic_loop.domain.enums import VerifierResult
from epistemic_loop.domain.models import BeliefUpdate


def clipped_probability(value: float) -> float:
    return min(0.95, max(0.05, value))


def update_probability(prior: float, evidence_weight: float) -> float:
    prior = clipped_probability(prior)
    log_odds = math.log(prior / (1 - prior))
    posterior = 1 / (1 + math.exp(-(log_odds + evidence_weight)))
    return clipped_probability(posterior)


def belief_update(
    hypothesis_id: str,
    prior: float,
    evidence: EvidenceLevel,
    summary: str,
    observation_ids: list[str],
    verifier_result: VerifierResult,
) -> BeliefUpdate:
    weight = EVIDENCE_WEIGHTS[evidence]
    if verifier_result == VerifierResult.FAIL:
        weight = 0.0
    elif verifier_result == VerifierResult.DISPUTED:
        weight *= 0.5
    return BeliefUpdate(
        id=f"BU-{uuid.uuid4().hex[:12]}",
        hypothesis_id=hypothesis_id,
        prior_confidence=prior,
        posterior_confidence=update_probability(prior, weight),
        update_method="log_odds_evidence",
        evidence_strength=weight,
        evidence_summary=summary,
        observation_ids=observation_ids,
        verifier_result=verifier_result,
    )
