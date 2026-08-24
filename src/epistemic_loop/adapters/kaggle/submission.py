from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SubmissionCandidate:
    name: str
    file: str
    priority: int = 100
    enabled: bool = True
    message: str | None = None


@dataclass(frozen=True)
class SubmissionPlan:
    competition: str
    daily_cap: int
    submitted_today: int
    remaining_today: int
    selected: SubmissionCandidate | None
    reason: str


def fingerprint(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plan_submission(
    competition: str,
    candidates: list[SubmissionCandidate],
    *,
    submitted_today: int,
    daily_cap: int,
    submitted_fingerprints: set[str] | None = None,
) -> SubmissionPlan:
    if daily_cap <= 0 or submitted_today < 0:
        raise ValueError("submission counts must be valid non-negative integers")
    remaining = max(0, daily_cap - submitted_today)
    if remaining == 0:
        return SubmissionPlan(competition, daily_cap, submitted_today, remaining, None, "daily cap reached")
    seen = submitted_fingerprints or set()
    eligible = [item for item in candidates if item.enabled and Path(item.file).is_file()]
    eligible.sort(key=lambda item: (item.priority, item.name))
    selected = next((item for item in eligible if fingerprint(item.file) not in seen), None)
    reason = "highest-priority new artifact" if selected else "no enabled, existing, unsubmitted artifact"
    return SubmissionPlan(competition, daily_cap, submitted_today, remaining, selected, reason)


class SubmissionLedger:
    """Append-only audit log used for cap and duplicate enforcement."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def append(self, record: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")

    def submitted_today(self, competition: str, now: datetime | None = None) -> int:
        day = (now or datetime.now(UTC)).date().isoformat()
        return sum(
            record.get("competition") == competition
            and str(record.get("created_at", "")).startswith(day)
            and record.get("mode") == "execute"
            for record in self.records()
        )

    def fingerprints(self, competition: str) -> set[str]:
        return {
            str(record["sha256"])
            for record in self.records()
            if record.get("competition") == competition and record.get("sha256")
        }


def plan_record(plan: SubmissionPlan) -> dict[str, Any]:
    value = asdict(plan)
    value["created_at"] = datetime.now(UTC).isoformat()
    return value
