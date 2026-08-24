from enum import StrEnum


class EvidenceLevel(StrEnum):
    DECISIVE_SUPPORT = "decisive_support"
    STRONG_SUPPORT = "strong_support"
    WEAK_SUPPORT = "weak_support"
    NEUTRAL = "neutral"
    WEAK_REFUTATION = "weak_refutation"
    STRONG_REFUTATION = "strong_refutation"
    DECISIVE_REFUTATION = "decisive_refutation"


EVIDENCE_WEIGHTS: dict[EvidenceLevel, float] = {
    EvidenceLevel.DECISIVE_SUPPORT: 2.0,
    EvidenceLevel.STRONG_SUPPORT: 1.0,
    EvidenceLevel.WEAK_SUPPORT: 0.5,
    EvidenceLevel.NEUTRAL: 0.0,
    EvidenceLevel.WEAK_REFUTATION: -0.5,
    EvidenceLevel.STRONG_REFUTATION: -1.0,
    EvidenceLevel.DECISIVE_REFUTATION: -2.0,
}
