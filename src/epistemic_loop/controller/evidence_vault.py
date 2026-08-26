from __future__ import annotations

from pathlib import Path

from epistemic_loop.domain.enums import CommunicationMode, EvidenceVisibility
from epistemic_loop.domain.models import (
    CommunicationPolicy,
    EvidencePromotionRequest,
    GlobalEvidence,
)


class EvidenceVault:
    """Central immutable observations; interpretations never enter this store."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def store(self, evidence: GlobalEvidence) -> Path:
        path = self._path(evidence.evidence_id)
        if path.exists():
            existing = GlobalEvidence.model_validate_json(path.read_text(encoding="utf-8"))
            if existing != evidence:
                raise ValueError(f"evidence is immutable: {evidence.evidence_id}")
            return path
        temporary = path.with_suffix(".tmp")
        temporary.write_text(evidence.model_dump_json(indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
        return path

    def get(self, evidence_id: str) -> GlobalEvidence:
        path = self._path(evidence_id)
        if not path.is_file():
            raise KeyError(f"unknown evidence: {evidence_id}")
        return GlobalEvidence.model_validate_json(path.read_text(encoding="utf-8"))

    def all(self) -> tuple[GlobalEvidence, ...]:
        return tuple(
            GlobalEvidence.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(self.root.glob("*.json"))
        )

    def promote(self, request: EvidencePromotionRequest) -> GlobalEvidence:
        evidence = self.get(request.evidence_id)
        verification = evidence.verification
        failed = []
        if not verification.artifact_contract_valid:
            failed.append("artifact contract is invalid")
        if not verification.independently_replicated:
            failed.append("observation is not independently replicated")
        if not verification.observation_interpretation_separated:
            failed.append("observation and interpretation are not separated")
        if not request.expected_compute_saving:
            failed.append("no expected computation saving")
        if request.diversity_risk > 0.5:
            failed.append("promotion would materially reduce search diversity")
        if evidence.structural_hypothesis_id and evidence.structure_validation_debt_open:
            failed.append("structural validation debt is open")
        if failed:
            raise ValueError("evidence cannot be promoted: " + "; ".join(failed))
        promoted = evidence.model_copy(update={"visibility": EvidenceVisibility.SHAREABLE_FACT})
        self._replace(promoted)
        return promoted

    def _replace(self, evidence: GlobalEvidence) -> None:
        path = self._path(evidence.evidence_id)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(evidence.model_dump_json(indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)

    def _path(self, identifier: str) -> Path:
        if not identifier or Path(identifier).name != identifier:
            raise ValueError("evidence_id must be a safe path component")
        return self.root / f"{identifier}.json"


class SelectiveEvidenceRouter:
    def __init__(self, policy: CommunicationPolicy | None = None):
        self.policy = policy or CommunicationPolicy()

    def route(
        self,
        evidence: GlobalEvidence,
        *,
        recipient_agent: str,
        current_cycle: int,
        phase_boundary: bool = False,
        controller: bool = False,
    ) -> GlobalEvidence | None:
        if controller or recipient_agent == evidence.producer_agent:
            return evidence
        if evidence.visibility == EvidenceVisibility.GLOBAL_SAFETY:
            return evidence
        if self.policy.mode == CommunicationMode.NO_SHARING:
            return None
        if self.policy.mode == CommunicationMode.FULL_LIVE_SHARING:
            return evidence
        if evidence.visibility == EvidenceVisibility.SHARED_CHALLENGE:
            if recipient_agent != evidence.challenge_target_agent:
                return None
            return self._hide_source(evidence)
        if evidence.visibility != EvidenceVisibility.SHAREABLE_FACT:
            return None
        migration_due = current_cycle >= evidence.created_cycle + self.policy.migration_interval_cycles
        if not phase_boundary and not migration_due:
            return None
        return evidence

    def migration(
        self,
        evidence: list[GlobalEvidence],
        *,
        recipient_agent: str,
        current_cycle: int,
        phase_boundary: bool = False,
    ) -> tuple[GlobalEvidence, ...]:
        routed = (
            self.route(
                item,
                recipient_agent=recipient_agent,
                current_cycle=current_cycle,
                phase_boundary=phase_boundary,
            )
            for item in evidence
        )
        return tuple(item for item in routed if item is not None)

    def _hide_source(self, evidence: GlobalEvidence) -> GlobalEvidence:
        if not self.policy.hide_source_agent_on_challenge:
            return evidence
        return evidence.model_copy(update={"producer_agent": "withheld"})
