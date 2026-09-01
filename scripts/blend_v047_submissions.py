#!/usr/bin/env python3
"""Rank-average N v0.4.7 submission.csv files into one blended submission.csv.

Mechanical, no agent involved (docs/c_lite_v047_policy.md SS2.3): each input file's
predictions are converted to within-file ranks (robust to scale/calibration differences
between candidates), then averaged and rescaled to [0,1]. Used for the 5th of the 5 daily
submission slots -- the other 4 are the individual candidates' own submissions.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, nargs="+", required=True, help="two or more submission.csv files")
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if len(arguments.inputs) < 2:
        raise SystemExit("need at least 2 input submissions to blend")

    frames = [pd.read_csv(path) for path in arguments.inputs]
    id_column, target_column = frames[0].columns
    for path, frame in zip(arguments.inputs, frames, strict=True):
        if list(frame.columns) != [id_column, target_column]:
            raise SystemExit(f"{path} has columns {list(frame.columns)}, expected [{id_column}, {target_column}]")
        if len(frame) != len(frames[0]):
            raise SystemExit(f"{path} has {len(frame)} rows, expected {len(frames[0])}")

    merged = frames[0][[id_column]].copy()
    for index, frame in enumerate(frames):
        ordered = frame.set_index(id_column).loc[merged[id_column]].reset_index()
        merged[f"rank_{index}"] = ordered[target_column].rank(pct=True)

    rank_columns = [f"rank_{index}" for index in range(len(frames))]
    merged[target_column] = merged[rank_columns].mean(axis=1)
    merged[[id_column, target_column]].to_csv(arguments.output, index=False, quoting=csv.QUOTE_MINIMAL)
    print(f"wrote {arguments.output} ({len(merged)} rows, blend of {len(arguments.inputs)} submissions)")


if __name__ == "__main__":
    main()
