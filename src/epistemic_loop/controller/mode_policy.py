from __future__ import annotations

from dataclasses import dataclass

from epistemic_loop.domain.enums import RunMode


@dataclass(frozen=True)
class ModeCapabilities:
    """Feature boundary for the four falsifiable system arms.

    Keeping this as a deterministic policy prevents an A/B run from acquiring
    epistemic behavior merely because a proposal happens to contain the newer
    schema fields.
    """

    performance_search: bool
    solution_qd: bool
    epistemic_descriptors: bool
    belief_posterior: bool
    information_value: bool
    independent_falsifier: bool
    oof_diversity: bool


SYSTEM_A = ModeCapabilities(True, False, False, False, False, False, False)
SYSTEM_B = ModeCapabilities(True, True, False, False, False, False, True)
SYSTEM_B_PLUS = ModeCapabilities(True, True, True, False, False, False, True)
SYSTEM_C = ModeCapabilities(True, True, True, True, True, True, True)


def capabilities(mode: RunMode) -> ModeCapabilities:
    if mode in {RunMode.SYSTEM_A, RunMode.EXPLOITER_ONLY}:
        return SYSTEM_A
    if mode == RunMode.SYSTEM_B:
        return SYSTEM_B
    if mode == RunMode.SYSTEM_B_PLUS:
        return SYSTEM_B_PLUS
    return SYSTEM_C
