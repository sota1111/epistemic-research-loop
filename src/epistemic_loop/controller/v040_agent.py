"""v0.4.0 agent contract: v0.3.9 plus null-referenced implication provenance.

The implication statistic was the last uncalibrated self-reported scalar in the
qualification (adversarial review, 2026-08-28). v0.4.0 requires that for every pack
with a terminal resolution, each context carries an implication provenance artifact:
the statistic's name, a held-out flag, its position within the agent's own
confounder-preserving null distribution, and a computation hash. Terminal resolutions
must be consistent with those positions. All checks use only the agent's own numbers.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from epistemic_loop.controller.v037_agent import (
    V037PackSubmission,
    V037Resolution,
    V037SubmissionValidation,
)
from epistemic_loop.controller.v038_agent import (
    V038LoadedSubmission,
    parse_v038_submission,
    validate_v038_submission,
)
from epistemic_loop.controller.v039_agent import (
    _validate_terminal_consistency,
    v039_submission_contract,
)

_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")

#: A null-referenced implication at or beyond this position supports structural presence.
IMPLICATION_NULL_POSITION_SUPPORT = 0.95

_PROMOTED = {
    V037Resolution.VALIDATED_ACTIONABLE_TRANSFERRED,
    V037Resolution.VALIDATED_ACTIONABLE_NOT_TRANSFERRED,
    V037Resolution.VALIDATED_NON_ACTIONABLE,
}


@dataclass(frozen=True)
class ImplicationProvenance:
    statistic: str
    held_out: bool
    null_reference_position: float
    computation_hash: str

    def __post_init__(self) -> None:
        if not self.statistic.strip():
            raise ValueError("implication statistic name is required")
        if not 0 <= self.null_reference_position <= 1:
            raise ValueError("null reference position must lie in [0,1]")
        if not _HASH_PATTERN.fullmatch(self.computation_hash):
            raise ValueError("computation_hash must be a lowercase sha256 hex digest")


@dataclass(frozen=True)
class V040LoadedSubmission:
    base: V038LoadedSubmission
    implication_provenance: Mapping[str, Mapping[str, ImplicationProvenance]]

    @property
    def core(self):  # type: ignore[no-untyped-def]
        return self.base.core

    @property
    def extras(self):  # type: ignore[no-untyped-def]
        return self.base.extras


def load_v040_submission(path: Path) -> V040LoadedSubmission:
    payload = json.loads(path.read_text())
    base = parse_v038_submission(payload, expected_version="0.4.0")
    provenance: dict[str, dict[str, ImplicationProvenance]] = {}
    for pack in payload.get("packs", ()):
        pack_id = str(pack.get("opaque_pack_id"))
        bucket: dict[str, ImplicationProvenance] = {}
        for context in pack.get("contexts", ()):
            raw = context.get("implication_provenance")
            if raw is None:
                continue
            bucket[str(context.get("opaque_context_id"))] = ImplicationProvenance(
                statistic=str(raw["statistic"]),
                held_out=bool(raw["held_out"]),
                null_reference_position=float(raw["null_reference_position"]),
                computation_hash=str(raw["computation_hash"]),
            )
        provenance[pack_id] = bucket
    return V040LoadedSubmission(base=base, implication_provenance=provenance)


def validate_v040_submission(
    loaded: V040LoadedSubmission,
    packet: dict[str, Any],
) -> V037SubmissionValidation:
    base = validate_v038_submission(loaded.base, packet, expected_packet_version="0.4.0")
    errors = list(base.errors)
    for pack in loaded.core.packs:
        errors.extend(_validate_terminal_consistency(pack))
        errors.extend(
            _validate_implication_provenance(pack, loaded.implication_provenance.get(pack.opaque_pack_id, {}))
        )
    return V037SubmissionValidation(not errors, tuple(errors))


def _validate_implication_provenance(
    pack: V037PackSubmission,
    provenance: Mapping[str, ImplicationProvenance],
) -> list[str]:
    prefix = pack.opaque_pack_id
    terminal = pack.resolution in _PROMOTED or pack.resolution is V037Resolution.FALSIFIED
    if not terminal:
        return []
    errors: list[str] = []
    positions: list[float] = []
    hashes: list[str] = []
    for context in pack.contexts:
        item = provenance.get(context.opaque_context_id)
        if item is None:
            errors.append(f"{prefix}/{context.opaque_context_id}: terminal resolution requires implication provenance")
            continue
        if not item.held_out:
            errors.append(f"{prefix}/{context.opaque_context_id}: implication statistic must be held-out")
        positions.append(item.null_reference_position)
        hashes.append(item.computation_hash)
    if len(hashes) != len(set(hashes)):
        errors.append(f"{prefix}: implication computation hashes must be unique per context")
    if len(positions) == len(pack.contexts):
        supported = sum(value >= IMPLICATION_NULL_POSITION_SUPPORT for value in positions)
        if pack.resolution is V037Resolution.FALSIFIED and supported >= 2:
            errors.append(
                f"{prefix}: falsified resolution conflicts with null-referenced implication positions "
                f">= {IMPLICATION_NULL_POSITION_SUPPORT} in {supported} contexts"
            )
        if pack.resolution in _PROMOTED and supported < 2:
            errors.append(
                f"{prefix}: a validated structure requires null-referenced implication positions "
                f">= {IMPLICATION_NULL_POSITION_SUPPORT} in at least two contexts; found {supported}"
            )
    return errors


def v040_submission_contract() -> dict[str, Any]:
    contract = v039_submission_contract()
    contract["version"] = "0.4.0"
    contract["context_fields"] = {
        **contract["context_fields"],
        "implication_provenance": (
            "required for every context of a pack with a terminal resolution: object with "
            "statistic (name), held_out (must be true), null_reference_position (position of the "
            "held-out implication statistic within your own confounder-preserving null distribution, "
            "in [0,1]), computation_hash (sha256 over the computation artifact)"
        ),
    }
    contract["implication_consistency"] = (
        f"a falsified pack may report a null-referenced implication position >= "
        f"{IMPLICATION_NULL_POSITION_SUPPORT} in at most one context; a validated pack must reach it "
        "in at least two contexts"
    )
    return contract
