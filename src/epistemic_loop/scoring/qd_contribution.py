"""Novelty as a measured contribution to the archive, not as a number the proposer supplies.

`docs/v050_course_correction.md` §3 item 11 -- the "strong B" prerequisite. §2.2 sets out what the
campaign actually ran against what it claimed to run: System B's utility is supposed to carry
novelty / QD contribution, and what it carried was `proposal.novelty_score`, a self-declared field.
An arm that scores its own novelty is not a quality-diversity arm; it is a performance arm with an
opinion, and "70 individuals and the solution families never split" follows from the design rather
than from the data.

The contribution here is measured against the archive the run already keeps: how much room is left
in the cell this proposal would land in. An empty cell is worth the full term; a cell already
holding its four elites is worth nothing, however novel the proposer believes the work to be.

The term is only available when the proposal declares its descriptors. That is deliberate: novelty
you did not specify in advance is novelty you cannot be held to, and falling back to the declared
score is recorded as such rather than passed off as a measurement
(`UtilityBreakdown.diversity_method`).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from epistemic_loop.domain.models import ExperimentProposal, QDCandidate
from epistemic_loop.qd.descriptors import cell_key

#: Elites the archive keeps per cell (`qd/archive.py`): best quality, lowest cost, highest
#: robustness, highest error diversity.
CELL_SLOTS = 4


def cell_census(candidates: Iterable[QDCandidate], descriptor_names: Sequence[str]) -> dict[str, int]:
    """How many retained candidates already occupy each cell."""
    census: dict[str, int] = {}
    for candidate in candidates:
        key = cell_key(candidate.descriptors, descriptor_names)
        census[key] = census.get(key, 0) + 1
    return census


def qd_contribution(
    proposal: ExperimentProposal,
    census: Mapping[str, int],
    descriptor_names: Sequence[str],
) -> float | None:
    """Room left in the cell this proposal would occupy, in [0, 1]; ``None`` when unmeasurable.

    ``None`` means "this proposal did not say where it would land", not "it would contribute
    nothing" -- the caller has to decide what to do with that, and record which it did.
    """
    if proposal.descriptors is None or not descriptor_names:
        return None
    occupied = census.get(cell_key(proposal.descriptors, descriptor_names), 0)
    return max(0.0, 1.0 - min(occupied, CELL_SLOTS) / CELL_SLOTS)
