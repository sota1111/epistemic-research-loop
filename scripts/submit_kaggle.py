#!/usr/bin/env python3
"""Thin wrapper around `kaggle competitions submit`.

Deliberately kept separate from prepare_kaggle_submission.py and never invoked
automatically by any other script in this project -- the actual real-world Kaggle
submission (a non-reversible use of that competition's finite daily quota) requires
explicit human confirmation each time, per docs/c_lite_v047_policy.md SS6/SS7. Run this by
hand once you've reviewed the submission.csv it's about to send.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--competition-ref", required=True, help="the real Kaggle competition slug, e.g. ieee-fraud-detection"
    )
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--message", required=True)
    arguments = parser.parse_args()
    if not arguments.file.exists():
        raise SystemExit(f"submission file not found: {arguments.file}")

    command = [
        "kaggle",
        "competitions",
        "submit",
        "-c",
        arguments.competition_ref,
        "-f",
        str(arguments.file),
        "-m",
        arguments.message,
    ]
    print("about to run:", " ".join(command))
    completed = subprocess.run(command, check=False)
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
