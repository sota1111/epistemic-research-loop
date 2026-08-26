from __future__ import annotations

import math
import uuid

from epistemic_loop.belief.evidence import EVIDENCE_WEIGHTS, EvidenceLevel
from epistemic_loop.domain.enums import VerifierResult
from epistemic_loop.domain.models import BeliefUpdate, OutcomeLikelihood


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


def bayesian_belief_update(
    hypothesis_id: str,
    prior: float,
    likelihood: OutcomeLikelihood,
    summary: str,
    observation_ids: list[str],
    verifier_result: VerifierResult,
    *,
    reliability: float = 1.0,
) -> BeliefUpdate:
    """Update from the outcome likelihood fixed before execution."""

    if not 0 < reliability <= 1:
        raise ValueError("evidence reliability must be in (0, 1]")
    if verifier_result == VerifierResult.FAIL:
        reliability = 0.0
    elif verifier_result == VerifierResult.DISPUTED:
        reliability *= 0.5
    safe_true = max(likelihood.probability_if_true, 1e-12)
    safe_false = max(likelihood.probability_if_false, 1e-12)
    log_bayes_factor = math.log(safe_true / safe_false) * reliability
    clipped_prior = clipped_probability(prior)
    prior_log_odds = math.log(clipped_prior / (1 - clipped_prior))
    posterior = clipped_probability(1 / (1 + math.exp(-(prior_log_odds + log_bayes_factor))))
    return BeliefUpdate(
        id=f"BU-{uuid.uuid4().hex[:12]}",
        hypothesis_id=hypothesis_id,
        prior_confidence=prior,
        posterior_confidence=posterior,
        update_method="bayesian_likelihood",
        evidence_strength=max(-2.0, min(2.0, log_bayes_factor)),
        evidence_summary=summary,
        observation_ids=observation_ids,
        verifier_result=verifier_result,
    )
