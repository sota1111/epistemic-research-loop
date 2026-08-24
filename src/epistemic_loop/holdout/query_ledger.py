from __future__ import annotations

import fcntl
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import Field

from epistemic_loop.domain.models import DomainModel, utc_now


class HoldoutQuery(DomainModel):
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    actor: str
    query_kind: str
    request: dict[str, Any]
    response_kind: str
    created_at: datetime = Field(default_factory=utc_now)


class QueryLedger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    def append(self, query: HoldoutQuery) -> None:
        with self.path.open("a", encoding="utf-8") as file:
            fcntl.flock(file.fileno(), fcntl.LOCK_EX)
            file.write(query.model_dump_json() + "\n")
            file.flush()
            os.fsync(file.fileno())
            fcntl.flock(file.fileno(), fcntl.LOCK_UN)

    def list(self, run_id: str | None = None) -> list[HoldoutQuery]:
        queries = [
            HoldoutQuery.model_validate_json(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return [item for item in queries if run_id is None or item.run_id == run_id]
