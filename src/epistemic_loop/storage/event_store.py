from __future__ import annotations

import fcntl
import hashlib
import json
import os
import uuid
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, TextIO

from epistemic_loop.domain.events import EventEnvelope, EventType
from epistemic_loop.domain.models import DomainModel, utc_now


def _canonical(data: dict[str, Any]) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


@contextmanager
def _locked(file: TextIO, exclusive: bool) -> Iterator[None]:
    fcntl.flock(file.fileno(), fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
    try:
        yield
    finally:
        fcntl.flock(file.fileno(), fcntl.LOCK_UN)


class IntegrityError(RuntimeError):
    pass


class JsonlEventStore:
    """Per-run append-only JSONL log with sequence and SHA-256 hash chaining."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    def _read_lines(self, file: TextIO) -> list[str]:
        file.seek(0)
        return [line for line in file.read().splitlines() if line.strip()]

    def append(
        self,
        run_id: str,
        event_type: EventType,
        payload: DomainModel | dict[str, Any],
    ) -> EventEnvelope:
        event_payload = payload.model_dump(mode="json") if isinstance(payload, DomainModel) else payload
        with self.path.open("r+", encoding="utf-8") as file, _locked(file, exclusive=True):
            lines = self._read_lines(file)
            prior = EventEnvelope.model_validate_json(lines[-1]) if lines else None
            sequence = (prior.sequence + 1) if prior else 1
            previous_hash = prior.event_hash if prior else None
            provisional = EventEnvelope(
                event_id=str(uuid.uuid4()),
                sequence=sequence,
                run_id=run_id,
                event_type=event_type,
                occurred_at=utc_now(),
                payload=event_payload,
                schema_version=1,
                previous_hash=previous_hash,
                event_hash="",
            )
            unsigned = provisional.model_dump(mode="json", exclude={"event_hash"})
            event_hash = hashlib.sha256(_canonical(unsigned)).hexdigest()
            envelope = provisional.model_copy(update={"event_hash": event_hash})
            file.seek(0, os.SEEK_END)
            file.write(envelope.model_dump_json() + "\n")
            file.flush()
            os.fsync(file.fileno())
            return envelope

    def read_all(self, verify: bool = True) -> list[EventEnvelope]:
        with self.path.open(encoding="utf-8") as file, _locked(file, exclusive=False):
            events = [EventEnvelope.model_validate_json(line) for line in self._read_lines(file)]
        if verify:
            self.verify(events)
        return events

    @staticmethod
    def verify(events: Iterable[EventEnvelope]) -> None:
        previous: str | None = None
        expected_sequence = 1
        for event in events:
            if event.sequence != expected_sequence:
                raise IntegrityError(f"sequence mismatch: expected {expected_sequence}, got {event.sequence}")
            if event.previous_hash != previous:
                raise IntegrityError(f"hash chain mismatch at sequence {event.sequence}")
            unsigned = event.model_dump(mode="json", exclude={"event_hash"})
            digest = hashlib.sha256(_canonical(unsigned)).hexdigest()
            if digest != event.event_hash:
                raise IntegrityError(f"event hash mismatch at sequence {event.sequence}")
            previous = event.event_hash
            expected_sequence += 1


def discover_event_stores(root: str | Path) -> Iterator[JsonlEventStore]:
    for event_file in sorted(Path(root).glob("*/events.jsonl")):
        yield JsonlEventStore(event_file)
