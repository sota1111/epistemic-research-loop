from __future__ import annotations

import csv
import json
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from epistemic_loop.adapters.kaggle.score_parser import parse_optional_score


@dataclass(frozen=True)
class SubmissionReceipt:
    competition: str
    submission_file: str
    message: str
    reference: str | None
    stdout: str


class KaggleCliSubmissionAdapter:
    """Evaluator-only wrapper. Never inject returned scores into a research run."""

    def __init__(self, runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run) -> None:
        self._run = runner

    def submit(self, competition: str, file: str | Path, message: str) -> SubmissionReceipt:
        submission = Path(file).resolve()
        if not submission.is_file():
            raise FileNotFoundError(submission)
        result = self._run(
            ["kaggle", "competitions", "submit", "-c", competition, "-f", str(file), "-m", message],
            check=True,
            capture_output=True,
            text=True,
        )
        reference = next((word for word in result.stdout.split() if word.isdigit()), None)
        return SubmissionReceipt(competition, str(submission), message, reference, result.stdout.strip())

    def submissions(self, competition: str, output_csv: str | Path) -> list[dict[str, object]]:
        destination = Path(output_csv)
        result = self._run(
            ["kaggle", "competitions", "submissions", "-c", competition, "--csv"],
            check=True,
            capture_output=True,
            text=True,
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(result.stdout, encoding="utf-8")
        with destination.open(newline="", encoding="utf-8-sig") as file:
            rows = list(csv.DictReader(file))
        return [
            {
                **row,
                "publicScore": parse_optional_score(row.get("publicScore")),
                "privateScore": parse_optional_score(row.get("privateScore")),
            }
            for row in rows
        ]

    def wait_for_terminal_status(
        self,
        competition: str,
        *,
        reference: str | None = None,
        timeout_seconds: float = 600,
        poll_seconds: float = 10,
    ) -> dict[str, object]:
        deadline = time.monotonic() + timeout_seconds
        while True:
            with tempfile.TemporaryDirectory(prefix="erl-kaggle-") as directory:
                rows = self.submissions(competition, Path(directory) / "submissions.csv")
            row = next((item for item in rows if reference is None or str(item.get("ref")) == reference), None)
            if row is not None:
                status = str(row.get("status", "")).lower()
                if any(value in status for value in ("complete", "error", "cancel")):
                    return row
            if time.monotonic() >= deadline:
                raise TimeoutError(f"submission did not finish within {timeout_seconds:g}s")
            time.sleep(poll_seconds)

    def leaderboard(self, competition: str) -> list[dict[str, str]]:
        result = self._run(
            ["kaggle", "competitions", "leaderboard", "-c", competition, "--show"],
            check=True,
            capture_output=True,
            text=True,
        )
        try:
            value = json.loads(result.stdout)
        except json.JSONDecodeError:
            return []
        return value if isinstance(value, list) else []
