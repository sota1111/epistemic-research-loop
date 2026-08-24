"""Evaluator-only submission automation. Research agents must not call these directly."""

from epistemic_loop.adapters.kaggle.cli import KaggleCliSubmissionAdapter, SubmissionReceipt
from epistemic_loop.adapters.kaggle.submission import (
    SubmissionCandidate,
    SubmissionLedger,
    SubmissionPlan,
    fingerprint,
    plan_submission,
)

__all__ = [
    "KaggleCliSubmissionAdapter",
    "SubmissionCandidate",
    "SubmissionLedger",
    "SubmissionPlan",
    "SubmissionReceipt",
    "fingerprint",
    "plan_submission",
]
