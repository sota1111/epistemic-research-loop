from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Hashable, Sequence
from typing import Any

from epistemic_loop.domain.models import FoldAssignment


def random_folds(
    row_ids: Sequence[str],
    *,
    world_id: str = "W-random",
    n_splits: int = 5,
    seed: int = 42,
) -> list[FoldAssignment]:
    """Deterministic shuffled K-fold assignments without a solver dependency."""

    _validate_rows(row_ids, n_splits)
    shuffled = list(row_ids)
    random.Random(seed).shuffle(shuffled)
    buckets = [shuffled[index::n_splits] for index in range(n_splits)]
    return _assignments(world_id, buckets)


def group_folds(
    row_ids: Sequence[str],
    groups: Sequence[Hashable],
    *,
    world_id: str = "W-group",
    n_splits: int = 5,
) -> list[FoldAssignment]:
    """Greedily balance whole groups across folds; a group never crosses a fold."""

    _validate_rows(row_ids, n_splits)
    if len(groups) != len(row_ids):
        raise ValueError("groups must align with row_ids")
    members: dict[Hashable, list[str]] = defaultdict(list)
    for row_id, group in zip(row_ids, groups, strict=True):
        members[group].append(row_id)
    if len(members) < n_splits:
        raise ValueError("group folds require at least one distinct group per split")
    buckets: list[list[str]] = [[] for _ in range(n_splits)]
    for _, rows in sorted(members.items(), key=lambda item: (-len(item[1]), repr(item[0]))):
        target = min(range(n_splits), key=lambda index: (len(buckets[index]), index))
        buckets[target].extend(rows)
    return _assignments(world_id, buckets)


def time_folds(
    row_ids: Sequence[str],
    timestamps: Sequence[Any],
    *,
    world_id: str = "W-time",
    n_splits: int = 4,
    gap_rows: int = 0,
) -> list[FoldAssignment]:
    """Expanding-window pseudo-future folds with an optional purge gap."""

    if len(timestamps) != len(row_ids):
        raise ValueError("timestamps must align with row_ids")
    if gap_rows < 0:
        raise ValueError("gap_rows must be non-negative")
    _validate_rows(row_ids, n_splits + 1)
    ordered = [row for _, row in sorted(zip(timestamps, row_ids, strict=True), key=lambda item: (item[0], item[1]))]
    # Split sorted positions into contiguous balanced time blocks.
    sizes = _balanced_sizes(len(ordered), n_splits + 1)
    blocks = []
    cursor = 0
    for size in sizes:
        blocks.append(ordered[cursor : cursor + size])
        cursor += size
    assignments: list[FoldAssignment] = []
    for index in range(n_splits):
        validation = blocks[index + 1]
        prior = [row for block in blocks[: index + 1] for row in block]
        purged = prior[-gap_rows:] if gap_rows else []
        train = prior[:-gap_rows] if gap_rows else prior
        if not train:
            raise ValueError("time fold purge gap leaves no training rows")
        assignments.append(
            FoldAssignment(
                world_id=world_id,
                fold_id=str(index),
                train_row_ids=train,
                validation_row_ids=validation,
                purged_row_ids=purged,
            )
        )
    return assignments


def time_group_folds(
    row_ids: Sequence[str],
    timestamps: Sequence[Any],
    groups: Sequence[Hashable],
    *,
    world_id: str = "W-time-group",
    n_splits: int = 4,
    gap_rows: int = 0,
) -> list[FoldAssignment]:
    """Time folds that additionally purge validation entities from training."""

    if len(groups) != len(row_ids):
        raise ValueError("groups must align with row_ids")
    by_row = dict(zip(row_ids, groups, strict=True))
    result = []
    for fold in time_folds(
        row_ids,
        timestamps,
        world_id=world_id,
        n_splits=n_splits,
        gap_rows=gap_rows,
    ):
        validation_groups = {by_row[row] for row in fold.validation_row_ids}
        entity_purge = [row for row in fold.train_row_ids if by_row[row] in validation_groups]
        train = [row for row in fold.train_row_ids if by_row[row] not in validation_groups]
        if not train:
            raise ValueError("time-group fold leaves no training rows after entity purge")
        result.append(
            fold.model_copy(update={"train_row_ids": train, "purged_row_ids": [*fold.purged_row_ids, *entity_purge]})
        )
    return result


def _assignments(world_id: str, validation_buckets: Sequence[Sequence[str]]) -> list[FoldAssignment]:
    all_rows = [row for bucket in validation_buckets for row in bucket]
    return [
        FoldAssignment(
            world_id=world_id,
            fold_id=str(index),
            train_row_ids=[row for row in all_rows if row not in set(validation)],
            validation_row_ids=list(validation),
        )
        for index, validation in enumerate(validation_buckets)
    ]


def _validate_rows(row_ids: Sequence[str], partitions: int) -> None:
    if partitions < 2:
        raise ValueError("at least two partitions are required")
    if len(row_ids) < partitions:
        raise ValueError("not enough rows for the requested partitions")
    if len(row_ids) != len(set(row_ids)):
        raise ValueError("row identifiers must be unique")


def _balanced_sizes(total: int, partitions: int) -> list[int]:
    quotient, remainder = divmod(total, partitions)
    return [quotient + int(index < remainder) for index in range(partitions)]
