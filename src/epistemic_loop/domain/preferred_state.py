"""Which research states the loop can actually measure, and which it only has a name for.

`docs/v050_course_correction.md` §1.2. The preferred state used to be seven hand-written constants
presented as a target vector. Two things were wrong with that and only one of them was the numbers.

The first is form. `research_models.md` §247 names a fixed target vector plus a numeric checklist
as the *most dangerous* shape this component can take, because it turns "what mattered in past
competitions" into "what every competition must score highly on". The corpus fitted in
`docs/world_model/` is a context-conditional distribution for exactly that reason.

The second is coverage, and it is the reason this module exists. The specification defines thirteen
states. The seven constants covered six of them; the other seven had no representation at all, and
nothing in the code said so -- a gap of zero against a state that was never measured is
indistinguishable from a state in perfect health. Absent targets are now **missing**, reported by
name, and never defaulted to a number.

Two of the thirteen are worse than missing: Hypothesis Calibration and Falsification Coverage were
observed **zero times** across the 38-competition corpus, because write-ups are composed after
success and do not carry the failed hypotheses or the confidence history
(`docs/world_model/results.md` §2.4). No amount of corpus work will supply a prior for them, and
they are the two states that distinguish C-lite from B. They can only come from an experiment.
"""

from __future__ import annotations

from collections.abc import Iterable
from types import MappingProxyType
from typing import Final

#: The thirteen research states of the specification (`research_models.md` §245), keyed by the
#: short names used in `docs/world_model/coding_rules.md` §2.
SPECIFICATION_STATES: Final[MappingProxyType[str, str]] = MappingProxyType(
    {
        "VF": "Validation Fidelity",
        "DGP": "DGP Understanding",
        "DSU": "Distribution Shift Understanding",
        "ETI": "Entity & Temporal Integrity",
        "DLQ": "Data / Label Quality Understanding",
        "EU": "Error Understanding",
        "HC": "Hypothesis Coverage",
        "HCAL": "Hypothesis Calibration",
        "FC": "Falsification Coverage",
        "RMC": "Representation / Model Coverage",
        "SED": "Solution / Error Diversity",
        "ROB": "Robustness",
        "PB": "Performance Belief",
    }
)

#: Dimensions `derive_research_state` computes from the event log, and the specification state each
#: one stands in for. ``None`` means the dimension is a loop metric with no state behind it.
MEASURED_DIMENSIONS: Final[MappingProxyType[str, str | None]] = MappingProxyType(
    {
        "validation_fidelity": "VF",
        "hypothesis_resolution": None,
        "falsification_coverage": "FC",
        "representation_coverage": "RMC",
        "error_diversity": "SED",
        "robustness": "ROB",
        "dgp_understanding": "DGP",
    }
)

#: Specification states with no measured dimension at all. Named here so that "we do not measure
#: this" is a fact in the code rather than an omission nobody can see.
UNMEASURED_STATES: Final[tuple[str, ...]] = tuple(
    key for key in SPECIFICATION_STATES if key not in set(MEASURED_DIMENSIONS.values())
)

#: States the winner corpus cannot supply a prior for at any corpus size
#: (`docs/world_model/results.md` §2.4). A target for either of these has to come from an
#: experiment, never from a fitted world model.
CORPUS_BLIND_STATES: Final[tuple[str, ...]] = ("HCAL", "FC")


def unknown_dimensions(names: Iterable[str]) -> tuple[str, ...]:
    """Names offered as preferred-state targets that the loop cannot compute."""
    return tuple(sorted(name for name in names if name not in MEASURED_DIMENSIONS))
