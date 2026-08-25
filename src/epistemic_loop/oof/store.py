from __future__ import annotations

import importlib
import json
import os
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

from epistemic_loop.domain.models import OOFRecord


class OOFStore:
    """Validated row-level OOF artifact store.

    JSONL is dependency-free and is the default audit format. Parquet is
    supported when the solver extra (pyarrow) is installed, without making the
    orchestration process import the training stack.
    """

    def write(self, path: str | Path, records: Iterable[OOFRecord]) -> Path:
        destination = Path(path)
        rows = list(records)
        _validate_rows(rows)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.suffix == ".parquet":
            self._write_parquet(destination, rows)
        else:
            self._write_jsonl(destination, rows)
        return destination

    def read(self, path: str | Path) -> list[OOFRecord]:
        source = Path(path)
        if source.suffix == ".parquet":
            rows = self._read_parquet(source)
        else:
            rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
        records = [OOFRecord.model_validate(item) for item in rows]
        _validate_rows(records)
        return records

    @staticmethod
    def _write_jsonl(destination: Path, rows: list[OOFRecord]) -> None:
        handle, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as file:
                for row in rows:
                    file.write(row.model_dump_json() + "\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_name, destination)
        except Exception:
            Path(temporary_name).unlink(missing_ok=True)
            raise

    @staticmethod
    def _write_parquet(destination: Path, rows: list[OOFRecord]) -> None:
        try:
            pa = importlib.import_module("pyarrow")
            pq = importlib.import_module("pyarrow.parquet")
        except ImportError as error:  # pragma: no cover - depends on optional solver extra
            raise RuntimeError("Parquet OOF storage requires `uv sync --extra solver`") from error
        table = pa.Table.from_pylist([item.model_dump(mode="json") for item in rows])
        pq.write_table(table, destination)

    @staticmethod
    def _read_parquet(source: Path) -> list[dict[str, Any]]:
        try:
            pq = importlib.import_module("pyarrow.parquet")
        except ImportError as error:  # pragma: no cover - depends on optional solver extra
            raise RuntimeError("Parquet OOF storage requires `uv sync --extra solver`") from error
        return cast(list[dict[str, Any]], pq.read_table(source).to_pylist())


def _validate_rows(rows: list[OOFRecord]) -> None:
    if not rows:
        raise ValueError("OOF artifact must contain at least one row")
    identities = [(item.candidate_id, item.validation_world, item.row_id) for item in rows]
    if len(identities) != len(set(identities)):
        raise ValueError("OOF rows must be unique per candidate, validation world, and row_id")
