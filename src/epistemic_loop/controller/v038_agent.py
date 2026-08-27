"""v0.3.8 agent contract: v0.3.7 plus machine-audited null provenance and lineage continuity.

The v0.3.8 submission is a strict superset of the v0.3.7 submission. Three additions are
contract-enforced before any output is locked:

1. Every executed null replicate must carry a per-replicate provenance artifact
   (permutation hash, preserved statistics, feature/fold/model/OOF hashes, gain).
   Self-declared booleans alone no longer satisfy the null contract.
2. Under ``posterior_commit`` and ``two_hit_maturation`` an open lineage must be
   followed in the next cycle or explicitly closed/falsified; the controller audits
   the selected lineage identifiers, not the agent-reported booleans.
3. Failure stages A-C are adjudicated by the controller from proposal artifacts in
   addition to the agent-reported failure trace.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from epistemic_loop.controller.v037_agent import (
    LineagePolicy,
    NullStoppingReason,
    V037AgentSubmission,
    V037PackSubmission,
    V037ResearchMode,
    V037SubmissionValidation,
    parse_v037_submission,
    v037_submission_contract,
    validate_v037_submission,
)

_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")

#: Lineage policies whose open lineages must be followed up in the next cycle.
DEEP_LINEAGE_POLICIES = (LineagePolicy.POSTERIOR_COMMIT, LineagePolicy.TWO_HIT_MATURATION)


@dataclass(frozen=True)
class NullReplicateProvenance:
    replicate_index: int
    permutation_hash: str
    preserved_statistics: Mapping[str, float]
    feature_manifest_hash: str
    fold_plan_hash: str
    model_fit_manifest_hash: str
    oof_prediction_hash: str
    gain: float

    def __post_init__(self) -> None:
        if self.replicate_index < 1:
            raise ValueError("replicate index must be one-based")
        for name, value in self.hash_fields().items():
            if not _HASH_PATTERN.fullmatch(value):
                raise ValueError(f"{name} must be a lowercase sha256 hex digest")
        if not self.preserved_statistics:
            raise ValueError("preserved statistics must be non-empty")
        if any(not math.isfinite(float(value)) for value in self.preserved_statistics.values()):
            raise ValueError("preserved statistics must be finite numbers")
        if not math.isfinite(self.gain):
            raise ValueError("replicate gain must be finite")

    def hash_fields(self) -> dict[str, str]:
        return {
            "permutation_hash": self.permutation_hash,
            "feature_manifest_hash": self.feature_manifest_hash,
            "fold_plan_hash": self.fold_plan_hash,
            "model_fit_manifest_hash": self.model_fit_manifest_hash,
            "oof_prediction_hash": self.oof_prediction_hash,
        }


@dataclass(frozen=True)
class V038SubmissionExtras:
    """v0.3.8-only structure that travels alongside the v0.3.7-compatible core."""

    declared_version: str
    provenance: Mapping[str, tuple[NullReplicateProvenance, ...]]


@dataclass(frozen=True)
class V038LoadedSubmission:
    core: V037AgentSubmission
    extras: V038SubmissionExtras


def load_v038_submission(path: Path) -> V038LoadedSubmission:
    payload = json.loads(path.read_text())
    declared_version = str(payload.get("version"))
    if declared_version != "0.3.8":
        raise ValueError(f"expected a v0.3.8 submission, found version {declared_version!r}")
    provenance: dict[str, tuple[NullReplicateProvenance, ...]] = {}
    for pack in payload.get("packs", ()):
        pack_id = str(pack.get("opaque_pack_id"))
        raw_replicates = pack.get("null_summary", {}).get("replicates", ())
        provenance[pack_id] = tuple(
            NullReplicateProvenance(
                replicate_index=int(item["replicate_index"]),
                permutation_hash=str(item["permutation_hash"]),
                preserved_statistics={
                    str(name): float(value) for name, value in dict(item["preserved_statistics"]).items()
                },
                feature_manifest_hash=str(item["feature_manifest_hash"]),
                fold_plan_hash=str(item["fold_plan_hash"]),
                model_fit_manifest_hash=str(item["model_fit_manifest_hash"]),
                oof_prediction_hash=str(item["oof_prediction_hash"]),
                gain=float(item["gain"]),
            )
            for item in raw_replicates
        )
    # The v0.3.7 dataclasses pin their version string; parse the shared core through the
    # locked v0.3.7 parser so every unchanged rule applies verbatim.
    compat = dict(payload)
    compat["version"] = "0.3.7"
    core = parse_v037_submission(compat)
    return V038LoadedSubmission(core=core, extras=V038SubmissionExtras(declared_version, provenance))


def validate_v038_submission(
    loaded: V038LoadedSubmission,
    packet: dict[str, Any],
) -> V037SubmissionValidation:
    base = validate_v037_submission(loaded.core, packet)
    errors = list(base.errors)
    if packet.get("version") != "0.3.8":
        errors.append("packet version mismatch")
    for pack in loaded.core.packs:
        errors.extend(_validate_pack_provenance(pack, loaded.extras.provenance.get(pack.opaque_pack_id, ())))
        errors.extend(_validate_lineage_continuity(pack, loaded.core.lineage_policy))
    return V037SubmissionValidation(not errors, tuple(errors))


def _validate_pack_provenance(
    pack: V037PackSubmission,
    replicates: tuple[NullReplicateProvenance, ...],
) -> list[str]:
    prefix = pack.opaque_pack_id
    if pack.null_summary.stopping_reason is NullStoppingReason.NOT_RUN:
        if replicates:
            return [f"{prefix}: not-run null must not carry provenance replicates"]
        return []
    errors: list[str] = []
    declared = pack.null_summary.replicate_gains
    if len(replicates) != len(declared):
        errors.append(f"{prefix}: provenance replicate count {len(replicates)} != declared {len(declared)}")
        return errors
    if tuple(item.replicate_index for item in replicates) != tuple(range(1, len(replicates) + 1)):
        errors.append(f"{prefix}: provenance replicate indices must be consecutive from one")
    for position, (item, gain) in enumerate(zip(replicates, declared, strict=True), start=1):
        if abs(item.gain - gain) > 1e-09:
            errors.append(f"{prefix}: replicate {position} gain does not match declared replicate gain")
    for field in (
        "permutation_hash",
        "feature_manifest_hash",
        "model_fit_manifest_hash",
        "oof_prediction_hash",
    ):
        values = [getattr(item, field) for item in replicates]
        if len(set(values)) != len(values):
            errors.append(f"{prefix}: {field} values must be unique across full-refit replicates")
    return errors


def _validate_lineage_continuity(pack: V037PackSubmission, policy: LineagePolicy) -> list[str]:
    if policy not in DEEP_LINEAGE_POLICIES:
        return []
    errors: list[str] = []
    for cycle, following in zip(pack.cycles, pack.cycles[1:], strict=False):
        if following.selected_lineage_id == cycle.selected_lineage_id:
            continue
        released = (
            cycle.lineage_explicitly_closed or cycle.falsification_evidence_added or cycle.converted_to_parent_or_final
        )
        if not released:
            errors.append(
                f"{pack.opaque_pack_id}: cycle {cycle.cycle} abandoned open lineage "
                f"{cycle.selected_lineage_id!r} without closing, falsifying, or maturing it"
            )
    return errors


def adjudicated_failure_trace(pack: V037PackSubmission) -> dict[str, bool]:
    """Controller-derived stages A-C from proposal artifacts instead of self-report."""

    proposals = [proposal for cycle in pack.cycles for proposal in cycle.proposals]
    hypothesis_generated = any(proposal.descriptor.structural_claim for proposal in proposals)
    discriminating_test_proposed = any(
        proposal.mode is V037ResearchMode.EPISTEMIC
        and proposal.discriminating_observable is not None
        and len(proposal.competing_hypotheses) >= 2
        for proposal in proposals
    )
    implementation_completed = len(pack.contexts) >= 3 and all(
        len(context.translations) >= 2 for context in pack.contexts
    )
    return {
        "hypothesis_generated": hypothesis_generated,
        "discriminating_test_proposed": discriminating_test_proposed,
        "implementation_completed": implementation_completed,
    }


def v038_submission_contract() -> dict[str, Any]:
    """Agent-visible contract: the v0.3.7 contract plus the v0.3.8 additions."""

    contract = v037_submission_contract()
    contract["version"] = "0.3.8"
    contract["null_summary"] = {
        **contract["null_summary"],
        "replicates": (
            "one provenance object per executed replicate, aligned with replicate_gains; "
            "required for every executed null"
        ),
    }
    contract["null_replicate_fields"] = {
        "replicate_index": "one-based consecutive integer",
        "permutation_hash": "sha256 hex of the destroyed-relation permutation",
        "preserved_statistics": "non-empty mapping of preserved confounder diagnostics to finite numbers",
        "feature_manifest_hash": "sha256 hex over the regenerated feature manifest",
        "fold_plan_hash": "sha256 hex over the fold plan",
        "model_fit_manifest_hash": "sha256 hex over the refit model manifest",
        "oof_prediction_hash": "sha256 hex over the out-of-fold predictions",
        "gain": "finite number equal to the aligned replicate_gains entry",
    }
    contract["lineage_continuity_rule"] = (
        "under posterior_commit or two_hit_maturation, a selected lineage that is not explicitly "
        "closed, falsified, or matured must be selected again in the next cycle; the controller "
        "audits selected_lineage_id sequences and rejects violations"
    )
    return contract
