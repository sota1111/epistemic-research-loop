"""Preregistered :class:`CompetitionSpec` instances for v0.4.2 multi-competition Track B.

Adding a new competition means adding one entry here (plus fetching its data, plus a
technique-taxonomy doc for post-hoc scoring) -- no other code changes, per
docs/c_lite_v042_policy.md SS3's "generalize the builder" intent.

Rossmann Store Sales is intentionally absent: its target (``Sales``) is a continuous
regression target, and this whole pipeline (AUC-based preflight/scoring, decile-stratified
permutation of a classifier's predicted probability) assumes a binary target. A
regression-metric variant is out of scope for v0.4.2's first round -- see
docs/c_lite_v042_policy.md SS3.
"""

from __future__ import annotations

from pathlib import Path

from epistemic_loop.benchmark.v042_multi_competition_suite import CompetitionSpec

IEEE_CIS = CompetitionSpec(
    competition_id="ieee-cis",
    data_path=Path(".data/ieee-cis/train_transaction.csv"),
    target_column="isFraud",
    id_columns=frozenset({"TransactionID"}),
    time_column="TransactionDT",
)

#: Santander's rows are not temporally ordered (its known epistemic challenge is a
#: synthetic/"fake test row" and transductive-statistics structure, per the user's own
#: candidate-table note) -- time_column=None selects the iid_random split strategy.
SANTANDER = CompetitionSpec(
    competition_id="santander-customer-transaction-prediction",
    data_path=Path(".data/santander-customer-transaction-prediction/train.csv"),
    target_column="target",
    id_columns=frozenset({"ID_code"}),
    time_column=None,
)

COMPETITION_REGISTRY: dict[str, CompetitionSpec] = {
    "ieee-cis": IEEE_CIS,
    "santander-customer-transaction-prediction": SANTANDER,
}
