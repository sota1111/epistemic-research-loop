from __future__ import annotations

import json
from collections.abc import Sequence

from epistemic_loop.controller.mode_policy import capabilities
from epistemic_loop.domain.enums import RunMode
from epistemic_loop.domain.models import CandidateDescriptors

SOLUTION_DESCRIPTORS = ("model_family", "representation", "data_scope")
EPISTEMIC_DESCRIPTORS = (
    "validation_type",
    "shift_hypothesis",
    "entity_hypothesis",
    "error_profile",
)
ALL_DESCRIPTORS = SOLUTION_DESCRIPTORS + EPISTEMIC_DESCRIPTORS


def descriptor_names_for_mode(mode: RunMode) -> tuple[str, ...]:
    policy = capabilities(mode)
    if not policy.solution_qd:
        return ()
    return ALL_DESCRIPTORS if policy.epistemic_descriptors else SOLUTION_DESCRIPTORS


def cell_key(descriptors: CandidateDescriptors, names: Sequence[str]) -> str:
    unknown = set(names) - set(ALL_DESCRIPTORS)
    if unknown:
        raise ValueError(f"unsupported QD descriptors: {sorted(unknown)}")
    if not names:
        raise ValueError("a QD cell requires at least one descriptor")
    values = {name: getattr(descriptors, name) for name in names}
    return json.dumps(values, sort_keys=True, separators=(",", ":"))
