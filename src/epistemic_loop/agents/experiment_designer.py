from __future__ import annotations

from typing import Protocol

from epistemic_loop.domain.models import ExperimentProposal, Hypothesis


class ExperimentDesigner(Protocol):
    def design(self, run_id: str, hypotheses: list[Hypothesis]) -> list[ExperimentProposal]: ...


def validate_preregistration(proposal: ExperimentProposal) -> None:
    if not proposal.predicted_outcomes:
        raise ValueError("experiment must preregister predicted outcomes")
    if not proposal.decision_rule.strip():
        raise ValueError("experiment must preregister a decision rule")
    if not proposal.controls:
        raise ValueError("experiment must define controls")
