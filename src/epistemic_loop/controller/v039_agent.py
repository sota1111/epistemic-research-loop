"""v0.3.9 agent contract: v0.3.8 plus terminal-resolution self-consistency.

The v0.3.8 qualification showed that most evidence-based rejections failed because the
falsification bundle contradicted itself: the agent declared ``falsified`` while its own
context artifacts reported an independent implication strength above 0.05 (73 of 95
blocked rejections), or research gains above its own full-refit null. v0.3.9 promotes
that internal-consistency requirement into the pre-lock contract. The check uses only
the agent's own submitted numbers — never controller truth — so repair feedback leaks
nothing about structures.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from epistemic_loop.controller.v037_agent import (
    NullStoppingReason,
    V037PackSubmission,
    V037Resolution,
    V037SubmissionValidation,
)
from epistemic_loop.controller.v038_agent import (
    V038LoadedSubmission,
    parse_v038_submission,
    v038_submission_contract,
    validate_v038_submission,
)

#: Implication strengths at or below this value are consistent with structural absence.
IMPLICATION_ABSENCE_THRESHOLD = 0.05

_PROMOTED = {
    V037Resolution.VALIDATED_ACTIONABLE_TRANSFERRED,
    V037Resolution.VALIDATED_ACTIONABLE_NOT_TRANSFERRED,
    V037Resolution.VALIDATED_NON_ACTIONABLE,
}


def load_v039_submission(path: Path) -> V038LoadedSubmission:
    return parse_v038_submission(json.loads(path.read_text()), expected_version="0.3.9")


def validate_v039_submission(
    loaded: V038LoadedSubmission,
    packet: dict[str, Any],
) -> V037SubmissionValidation:
    base = validate_v038_submission(loaded, packet, expected_packet_version="0.3.9")
    errors = list(base.errors)
    for pack in loaded.core.packs:
        errors.extend(_validate_terminal_consistency(pack))
    return V037SubmissionValidation(not errors, tuple(errors))


def _validate_terminal_consistency(pack: V037PackSubmission) -> list[str]:
    prefix = pack.opaque_pack_id
    strengths = [context.independent_implication_strength for context in pack.contexts]
    high_implication = sum(value > IMPLICATION_ABSENCE_THRESHOLD for value in strengths)
    errors: list[str] = []
    if pack.resolution is V037Resolution.FALSIFIED:
        if high_implication >= 2:
            errors.append(
                f"{prefix}: falsified resolution conflicts with your own independent implication "
                f"strengths above {IMPLICATION_ABSENCE_THRESHOLD} in {high_implication} contexts; "
                "either the implication measurement does not measure the claimed structure or the "
                "resolution is premature — re-examine and make the bundle consistent"
            )
        null_threshold = _own_null_95th(pack)
        research_high = sum(context.research_gain > null_threshold for context in pack.contexts)
        if research_high >= 2:
            errors.append(
                f"{prefix}: falsified resolution conflicts with research gains above your own "
                f"full-refit null 95th percentile in {research_high} contexts; re-examine the "
                "null design or the resolution"
            )
    if pack.resolution in _PROMOTED and high_implication < 2:
        errors.append(
            f"{prefix}: a validated structure requires an independent implication strength above "
            f"{IMPLICATION_ABSENCE_THRESHOLD} in at least two contexts; your artifacts report "
            f"{high_implication}"
        )
    return errors


def _own_null_95th(pack: V037PackSubmission) -> float:
    if pack.null_summary.stopping_reason is NullStoppingReason.NOT_RUN:
        return math.inf
    values = sorted(pack.null_summary.replicate_gains)
    if not values:
        return math.inf
    index = min(len(values) - 1, max(0, math.ceil(0.95 * len(values)) - 1))
    return values[index]


def v039_submission_contract() -> dict[str, Any]:
    contract = v038_submission_contract()
    contract["version"] = "0.3.9"
    contract["terminal_resolution_consistency"] = (
        "a falsified pack must report independent implication strengths consistent with absence "
        f"(at most one context above {IMPLICATION_ABSENCE_THRESHOLD}) and research gains within "
        "your own full-refit null in at least two of three contexts; a validated pack must report "
        f"independent implication strengths above {IMPLICATION_ABSENCE_THRESHOLD} in at least two "
        "contexts. Inconsistent bundles are rejected before lock."
    )
    return contract
