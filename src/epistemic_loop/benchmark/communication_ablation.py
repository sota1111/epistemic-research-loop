from __future__ import annotations

from dataclasses import dataclass

from epistemic_loop.domain.enums import CommunicationMode


@dataclass(frozen=True)
class CommunicationArmResult:
    mode: CommunicationMode
    hidden_performance: float
    semantic_duplication_rate: float
    hypothesis_diversity: float


@dataclass(frozen=True)
class CommunicationAblationDecision:
    selective_adopted: bool
    reasons: tuple[str, ...]


def evaluate_selective_sharing(
    no_sharing: CommunicationArmResult,
    selective: CommunicationArmResult,
    full_sharing: CommunicationArmResult,
) -> CommunicationAblationDecision:
    if no_sharing.mode != CommunicationMode.NO_SHARING:
        raise ValueError("no_sharing result has the wrong communication mode")
    if selective.mode != CommunicationMode.SELECTIVE_DELAYED_ASYMMETRIC:
        raise ValueError("selective result has the wrong communication mode")
    if full_sharing.mode != CommunicationMode.FULL_LIVE_SHARING:
        raise ValueError("full_sharing result has the wrong communication mode")
    checks = {
        "hidden performance is not below Comm-0": selective.hidden_performance >= no_sharing.hidden_performance,
        "semantic duplication is below Comm-0": (
            selective.semantic_duplication_rate < no_sharing.semantic_duplication_rate
        ),
        "hypothesis diversity is above Comm-F": selective.hypothesis_diversity > full_sharing.hypothesis_diversity,
    }
    failed = tuple(reason for reason, passed in checks.items() if not passed)
    return CommunicationAblationDecision(not failed, failed)
