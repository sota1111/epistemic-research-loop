from __future__ import annotations

from epistemic_loop.belief.evidence import EvidenceLevel
from epistemic_loop.domain.enums import FalsificationDisposition
from epistemic_loop.domain.models import FalsificationRecord


def interpret_evidence(record: FalsificationRecord) -> EvidenceLevel:
    if record.disposition == FalsificationDisposition.FALSIFIED:
        return EvidenceLevel.STRONG_REFUTATION
    if record.disposition == FalsificationDisposition.WEAKENED:
        return EvidenceLevel.WEAK_REFUTATION
    if record.disposition == FalsificationDisposition.SURVIVES:
        return EvidenceLevel.WEAK_SUPPORT
    return EvidenceLevel.NEUTRAL
