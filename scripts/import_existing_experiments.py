"""Import helper intentionally requires explicit mapping to preregistered hypotheses."""

import json
import sys


def main() -> None:
    payload = json.load(sys.stdin)
    if not payload.get("hypothesis_ids"):
        raise SystemExit("historical imports require hypothesis_ids and are marked retrospective")
    payload["retrospective"] = True
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
