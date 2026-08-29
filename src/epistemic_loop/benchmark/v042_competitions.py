"""Preregistered :class:`CompetitionSpec` instances for v0.4.2/v0.4.3 multi-competition Track B.

Adding a new competition means adding one entry here (plus fetching its data, plus a
technique-taxonomy doc for post-hoc scoring) -- no other code changes, per
docs/c_lite_v042_policy.md SS3's "generalize the builder" intent.
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

#: Regression target (v0.4.3-c, docs/verification/v043_rossmann_regression_preregistration.md).
#: ``Customers`` is excluded via ``id_columns`` -- not a hand-picked technique, but a data-
#: provenance fact: the real Kaggle test.csv has no ``Customers`` column (unobservable at
#: prediction time), so including it would be near-total leakage (Sales is ~linear in it).
ROSSMANN = CompetitionSpec(
    competition_id="rossmann-store-sales",
    data_path=Path(".data/rossmann-store-sales/train.csv"),
    target_column="Sales",
    id_columns=frozenset({"Customers"}),
    time_column="Date",
    task_type="regression",
)

COMPETITION_REGISTRY: dict[str, CompetitionSpec] = {
    "ieee-cis": IEEE_CIS,
    "santander-customer-transaction-prediction": SANTANDER,
    "rossmann-store-sales": ROSSMANN,
}
