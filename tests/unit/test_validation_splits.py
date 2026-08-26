import pytest

from epistemic_loop.validation.splits import group_folds, random_folds, time_folds, time_group_folds


def test_random_folds_are_seeded_disjoint_and_exhaustive() -> None:
    rows = [str(index) for index in range(20)]
    first = random_folds(rows, n_splits=4, seed=17)
    second = random_folds(rows, n_splits=4, seed=17)

    assert first == second
    assert {row for fold in first for row in fold.validation_row_ids} == set(rows)
    assert len([row for fold in first for row in fold.validation_row_ids]) == len(rows)
    assert all(set(fold.train_row_ids).isdisjoint(fold.validation_row_ids) for fold in first)


def test_group_folds_never_split_an_entity() -> None:
    rows = [f"r{index}" for index in range(12)]
    groups = [f"g{index // 2}" for index in range(12)]
    folds = group_folds(rows, groups, n_splits=3)
    group_by_row = dict(zip(rows, groups, strict=True))

    for fold in folds:
        train_groups = {group_by_row[row] for row in fold.train_row_ids}
        validation_groups = {group_by_row[row] for row in fold.validation_row_ids}
        assert train_groups.isdisjoint(validation_groups)


def test_time_folds_are_expanding_future_windows_with_a_purge_gap() -> None:
    rows = [f"r{index}" for index in range(15)]
    positions = {row: index for index, row in enumerate(rows)}
    folds = time_folds(rows, list(range(15)), n_splits=4, gap_rows=1)

    for fold in folds:
        assert max(positions[row] for row in fold.train_row_ids) < min(
            positions[row] for row in fold.validation_row_ids
        )
        assert len(fold.purged_row_ids) == 1
        assert max(positions[row] for row in fold.train_row_ids) < positions[fold.purged_row_ids[0]]


def test_time_group_folds_purge_future_entities_from_training() -> None:
    rows = [f"r{index}" for index in range(18)]
    groups = [f"g{index // 3}" for index in range(18)]
    group_by_row = dict(zip(rows, groups, strict=True))
    folds = time_group_folds(rows, list(range(18)), groups, n_splits=3)

    for fold in folds:
        train_groups = {group_by_row[row] for row in fold.train_row_ids}
        validation_groups = {group_by_row[row] for row in fold.validation_row_ids}
        assert train_groups.isdisjoint(validation_groups)


def test_fold_builders_reject_duplicate_row_identity() -> None:
    with pytest.raises(ValueError, match="unique"):
        random_folds(["same", "same", "other"], n_splits=2)
