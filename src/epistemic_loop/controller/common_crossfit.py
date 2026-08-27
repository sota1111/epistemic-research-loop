"""Stable research/sealed partition and common expanding-time fold plans."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass

SECONDS_PER_DAY = 86_400
V034_MODEL_SEEDS = (17, 42, 20260826)


@dataclass(frozen=True, order=True)
class OrderedRow:
    transaction_dt: int
    transaction_id: int


@dataclass(frozen=True)
class ResearchSealedPartition:
    research_rows: tuple[OrderedRow, ...]
    sealed_rows: tuple[OrderedRow, ...]
    research_row_set_sha256: str
    sealed_row_set_sha256: str
    partition_sha256: str
    research_fraction: float = 0.8

    @classmethod
    def build(
        cls,
        rows: Sequence[OrderedRow],
        *,
        research_fraction: float = 0.8,
    ) -> ResearchSealedPartition:
        if not 0 < research_fraction < 1:
            raise ValueError("research_fraction must be between zero and one")
        ordered = tuple(sorted(rows, key=lambda item: (item.transaction_dt, item.transaction_id)))
        if len({item.transaction_id for item in ordered}) != len(ordered):
            raise ValueError("TransactionID values must be unique")
        cut = int(len(ordered) * research_fraction)
        if cut < 4 or cut == len(ordered):
            raise ValueError("partition requires at least four research rows and one sealed row")
        research = ordered[:cut]
        sealed = ordered[cut:]
        research_hash = _row_hash(research)
        sealed_hash = _row_hash(sealed)
        stable = {
            "stable_sort": ["TransactionDT", "TransactionID"],
            "research_fraction": research_fraction,
            "research_row_set_sha256": research_hash,
            "sealed_row_set_sha256": sealed_hash,
        }
        return cls(
            research,
            sealed,
            research_hash,
            sealed_hash,
            _json_hash(stable),
            research_fraction,
        )


@dataclass(frozen=True)
class CommonForwardFold:
    fold_id: str
    train_transaction_ids: tuple[int, ...]
    evaluation_transaction_ids: tuple[int, ...]
    train_max_transaction_dt: int
    evaluation_min_transaction_dt: int
    train_rows_sha256: str
    evaluation_rows_sha256: str


@dataclass(frozen=True)
class CommonCrossfitPlan:
    folds: tuple[CommonForwardFold, ...]
    horizons: int
    minimum_gap_days: int
    model_seeds: tuple[int, ...]
    research_row_set_sha256: str
    fold_plan_sha256: str
    stable_sort: tuple[str, str] = ("TransactionDT", "TransactionID")

    @classmethod
    def build(
        cls,
        partition: ResearchSealedPartition,
        *,
        horizons: int = 3,
        minimum_gap_days: int = 7,
        model_seeds: Sequence[int] = V034_MODEL_SEEDS,
    ) -> CommonCrossfitPlan:
        if horizons < 3:
            raise ValueError("v0.3.4 common cross-fit requires at least three horizons")
        if minimum_gap_days < 0:
            raise ValueError("minimum_gap_days cannot be negative")
        seeds = tuple(model_seeds)
        if len(seeds) < 3 or len(set(seeds)) != len(seeds):
            raise ValueError("common cross-fit requires at least three unique model seeds")
        rows = partition.research_rows
        boundaries = [round(index * len(rows) / (horizons + 1)) for index in range(horizons + 2)]
        folds: list[CommonForwardFold] = []
        gap_seconds = minimum_gap_days * SECONDS_PER_DAY
        for horizon in range(1, horizons + 1):
            evaluation = rows[boundaries[horizon] : boundaries[horizon + 1]]
            if not evaluation:
                raise ValueError("research region is too small for the requested horizons")
            evaluation_min = evaluation[0].transaction_dt
            training = tuple(
                item for item in rows[: boundaries[horizon]] if item.transaction_dt < evaluation_min - gap_seconds
            )
            if not training:
                raise ValueError("time gap leaves a common fold without training rows")
            if training[-1].transaction_dt >= evaluation_min:
                raise ValueError("common fold is not past-only")
            folds.append(
                CommonForwardFold(
                    fold_id=f"forward-{horizon}",
                    train_transaction_ids=tuple(item.transaction_id for item in training),
                    evaluation_transaction_ids=tuple(item.transaction_id for item in evaluation),
                    train_max_transaction_dt=training[-1].transaction_dt,
                    evaluation_min_transaction_dt=evaluation_min,
                    train_rows_sha256=_row_hash(training),
                    evaluation_rows_sha256=_row_hash(evaluation),
                )
            )
        stable = {
            "folds": [asdict(item) for item in folds],
            "horizons": horizons,
            "minimum_gap_days": minimum_gap_days,
            "model_seeds": seeds,
            "research_row_set_sha256": partition.research_row_set_sha256,
            "stable_sort": ["TransactionDT", "TransactionID"],
        }
        return cls(
            tuple(folds),
            horizons,
            minimum_gap_days,
            seeds,
            partition.research_row_set_sha256,
            _json_hash(stable),
        )

    def verify_past_only(self) -> bool:
        gap_seconds = self.minimum_gap_days * SECONDS_PER_DAY
        return all(
            fold.train_max_transaction_dt < fold.evaluation_min_transaction_dt - gap_seconds for fold in self.folds
        )


def _row_hash(rows: Sequence[OrderedRow]) -> str:
    return _json_hash([(item.transaction_dt, item.transaction_id) for item in rows])


def _json_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
