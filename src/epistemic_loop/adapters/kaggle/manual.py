from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path


def manual_submission_packet(
    submission: str | Path,
    *,
    competition_slug: str,
    message: str,
    run_id: str,
    deadline: datetime | None = None,
) -> dict[str, object]:
    path = Path(submission)
    if not path.is_file():
        raise FileNotFoundError(path)
    return {
        "submission_file": str(path.resolve()),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "competition_slug": competition_slug,
        "message": message,
        "run_id": run_id,
        "deadline": deadline.isoformat() if deadline else None,
        "score_input_template": {"public_score": None, "private_score": None, "status": "pending_manual_input"},
    }


def write_manual_packet(packet: dict[str, object], destination: str | Path) -> None:
    Path(destination).write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
