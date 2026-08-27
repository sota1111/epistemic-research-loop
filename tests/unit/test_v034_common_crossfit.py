from __future__ import annotations

import pytest

from epistemic_loop.controller.common_crossfit import (
    SECONDS_PER_DAY,
    CommonCrossfitPlan,
    OrderedRow,
    ResearchSealedPartition,
)


def _rows(count: int = 100) -> list[OrderedRow]:
    return [OrderedRow(index * 2 * SECONDS_PER_DAY, 10_000 + index) for index in reversed(range(count))]


def test_partition_is_stable_and_sealed_tail_is_not_in_common_folds() -> None:
    partition = ResearchSealedPartition.build(_rows())
    plan = CommonCrossfitPlan.build(partition)

    assert len(partition.research_rows) == 80
    assert len(partition.sealed_rows) == 20
    assert partition.research_rows[0].transaction_id == 10_000
    assert plan.horizons == 3
    assert plan.model_seeds == (17, 42, 20260826)
    assert plan.verify_past_only()
    sealed_ids = {row.transaction_id for row in partition.sealed_rows}
    assert all(not sealed_ids.intersection(fold.evaluation_transaction_ids) for fold in plan.folds)


def test_partition_rejects_duplicate_ids_and_too_few_seeds() -> None:
    with pytest.raises(ValueError, match="unique"):
        ResearchSealedPartition.build([OrderedRow(1, 1), OrderedRow(2, 1), *[OrderedRow(i, i) for i in range(3, 10)]])
    partition = ResearchSealedPartition.build(_rows())
    with pytest.raises(ValueError, match="three unique"):
        CommonCrossfitPlan.build(partition, model_seeds=(1, 2))
