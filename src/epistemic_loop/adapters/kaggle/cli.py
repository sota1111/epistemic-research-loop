from __future__ import annotations

import csv
import subprocess
from pathlib import Path

from epistemic_loop.adapters.kaggle.score_parser import parse_optional_score


class KaggleCliSubmissionAdapter:
    """Evaluator-only wrapper. Never inject returned scores into a research run."""

    def submit(self, competition: str, file: str | Path, message: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["kaggle", "competitions", "submit", "-c", competition, "-f", str(file), "-m", message],
            check=True,
            capture_output=True,
            text=True,
        )

    def submissions(self, competition: str, output_csv: str | Path) -> list[dict[str, object]]:
        destination = Path(output_csv)
        subprocess.run(
            ["kaggle", "competitions", "submissions", "-c", competition, "--csv", "-v"],
            check=True,
            cwd=destination.parent,
            capture_output=True,
            text=True,
        )
        with destination.open(newline="", encoding="utf-8") as file:
            rows = list(csv.DictReader(file))
        return [
            {
                **row,
                "publicScore": parse_optional_score(row.get("publicScore")),
                "privateScore": parse_optional_score(row.get("privateScore")),
            }
            for row in rows
        ]
