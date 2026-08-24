"""Convert the IEEE-CIS CSVs to column-oriented parquet once.

Every experiment in a research loop reloads the data. Reading 683 MB of CSV per experiment would
make the loop's cadence a property of pandas rather than of the research, so this runs once and each
experiment afterwards reads only the columns its hypothesis needs.

This is preparation, not feature engineering: dtypes are narrowed and the identity table is joined,
and nothing else. Anything that could change what an experiment measures belongs in the experiment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

DEFAULT_ROOT = Path(".data/ieee-cis")
TARGET = "isFraud"
KEY = "TransactionID"
TIME = "TransactionDT"


def _narrow(frame: pd.DataFrame) -> pd.DataFrame:
    """Halve memory without changing any value: float64 -> float32, objects -> category."""
    for column in frame.columns:
        kind = frame[column].dtype
        if kind == "float64":
            frame[column] = frame[column].astype("float32")
        elif kind == "int64" and column not in {KEY, TIME}:
            frame[column] = pd.to_numeric(frame[column], downcast="integer")
        elif kind == "object":
            frame[column] = frame[column].astype("category")
    return frame


def _fingerprint(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.name.encode())
        digest.update(str(path.stat().st_size).encode())
    return digest.hexdigest()


def prepare(root: Path, destination: Path) -> dict[str, object]:
    destination.mkdir(parents=True, exist_ok=True)
    written: dict[str, object] = {}
    for split in ("train", "test"):
        transactions = pd.read_csv(root / f"{split}_transaction.csv")
        identity = pd.read_csv(root / f"{split}_identity.csv")
        # The test identity table renames id_01 to id-01; align it so one experiment spec works on both.
        identity.columns = [column.replace("-", "_") for column in identity.columns]
        merged = _narrow(transactions.merge(identity, on=KEY, how="left"))
        out = destination / f"{split}.parquet"
        merged.to_parquet(out, index=False)
        written[split] = {"rows": int(len(merged)), "columns": int(merged.shape[1]), "path": str(out)}
        del merged, transactions, identity

    manifest = {
        "source": str(root),
        "dataset_fingerprint": _fingerprint(list(root.glob("*.csv"))),
        "splits": written,
        "target": TARGET,
        "key": KEY,
        "time_column": TIME,
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="directory holding the Kaggle CSVs")
    parser.add_argument("--destination", type=Path, default=DEFAULT_ROOT / "parquet")
    arguments = parser.parse_args()
    print(json.dumps(prepare(arguments.root, arguments.destination), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
