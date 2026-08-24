from __future__ import annotations

import argparse
import json
import os

from epistemic_loop.holdout.sealed_store import SealedScoreStore


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("score_id")
    parser.add_argument("payload")
    parser.add_argument("--root", default=".sealed")
    parser.add_argument("--token-env", default="BENCHMARK_UNSEAL_TOKEN")
    args = parser.parse_args()
    token = os.environ.get(args.token_env)
    if not token:
        raise SystemExit(f"{args.token_env} is not set")
    path = SealedScoreStore(args.root).seal(args.score_id, json.loads(args.payload), token)
    print(path)


if __name__ == "__main__":
    main()
