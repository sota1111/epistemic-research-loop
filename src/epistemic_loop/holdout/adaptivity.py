from __future__ import annotations

import hashlib
import re
from collections import Counter

from epistemic_loop.domain.enums import ExperimentType
from epistemic_loop.domain.models import ExperimentProposal

#: Experiment types that do not pick a winner on the split and therefore do not consume adaptivity.
NON_SELECTING_TYPES = frozenset(
    {
        ExperimentType.DIAGNOSTIC,
        ExperimentType.FALSIFICATION,
        ExperimentType.REPLICATION,
        ExperimentType.ROBUSTNESS,
    }
)


def validation_fingerprint(proposal: ExperimentProposal) -> str:
    """Identity of the validation scheme an experiment is scored against.

    Only the split strategy and the metrics matter here; two experiments that train different models
    against the same split and the same metric are two adaptive queries to one validation set.
    """
    normalized = re.sub(r"\s+", " ", proposal.split_strategy).strip().casefold()
    identity = f"{normalized}|{'|'.join(sorted(metric.casefold() for metric in proposal.metrics))}"
    return hashlib.sha256(identity.encode()).hexdigest()


def validation_reuse(
    proposals: dict[str, ExperimentProposal],
    settled_ids: frozenset[str],
) -> dict[str, int]:
    """Selecting queries already spent against each validation scheme.

    Only committed experiments count: a proposal that was scored and never run never saw the split.
    """
    counts: Counter[str] = Counter()
    for identifier, proposal in proposals.items():
        if identifier in settled_ids and proposal.experiment_type not in NON_SELECTING_TYPES:
            counts[validation_fingerprint(proposal)] += 1
    return dict(counts)


def consumes_adaptivity(proposal: ExperimentProposal) -> bool:
    return proposal.experiment_type not in NON_SELECTING_TYPES


def exhausted(proposal: ExperimentProposal, reuse: dict[str, int], budget: int) -> bool:
    """Whether one more selecting query would exceed this validation scheme's adaptivity budget.

    Reusing one validation split to choose between many candidates is exactly the adaptive data
    analysis that makes a reported CV gain optimistic: the winner is partly fitted to the split's
    noise. A budget forces the run either to rotate the split or to spend a diagnostic on whether
    the split still means what it did, instead of quietly grinding the same numbers.
    """
    if budget <= 0:
        return False
    if not consumes_adaptivity(proposal):
        return False
    return reuse.get(validation_fingerprint(proposal), 0) >= budget
