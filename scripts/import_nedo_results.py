#!/usr/bin/env python3
"""Load the NEDO loading campaign's scored runs into the engine's per-task score store.

The campaign kept exactly what `docs/v050_course_correction.md` §3 item 4 asks for -- a raw metric
vector per task per individual -- but it kept it in its own format, read by its own tools. This
converts it once, so the engine's resolution gate (`erlctl measure rank`) can be pointed at the
real campaign data instead of at a demonstration.

Nothing here is NEDO-specific except the field names and the scoring specification, both of which
are written out alongside the scores so a later recomputation does not have to rediscover them.

    uv run python scripts/import_nedo_results.py \\
        --results ~/dev/2026/erl-nedo-baggage-loading/results/all48 \\
        --out .data/nedo/all48.jsonl

The gate matters and is not cosmetic: below a placed-item fraction the competition's scoring drops
every component except fill, so a plain weighted sum reproduces neither the ranking nor the
campaign's own composite. `--verify` checks the derived composite against the number each file
already carries, which is the only way to know the conversion preserved the scoring.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from epistemic_loop.measurement.task_scores import CompositeSpec, TaskGate, TaskScore, TaskScoreStore, composite_scores

#: Raw per-task measurements the campaign records. `*_raw` holds the value before the gate zeroed
#: it, so that is the raw vector; the un-suffixed key is already a derived, gated number.
RAW_METRICS = ("fill_score", "cog_score", "placement_score", "soft_item_score", "stability_score")
GATE_METRIC = "num_placed_items"


def _raw_vector(evaluation: dict[str, Any]) -> dict[str, float]:
    vector = {name: float(evaluation.get(f"{name}_raw", evaluation[name])) for name in RAW_METRICS}
    vector[GATE_METRIC] = float(evaluation[GATE_METRIC])
    return vector


def composite_spec(document: dict[str, Any]) -> CompositeSpec:
    """The scoring specification the run was scored under, read off the run itself."""
    summary = document["summary"]
    weights = summary["scoring_weights"]
    threshold = float(summary.get("min_placed_fraction", summary["scoring_config"]["min_placed_fraction"]))
    # placement and soft share one weight, averaged. That is a linear combination, so it stays in
    # the weights rather than becoming a special case in the derivation.
    return CompositeSpec(
        weights={
            "fill_score": float(weights["fill"]),
            "cog_score": float(weights["cog"]),
            "placement_score": float(weights["placement"]) / 2,
            "soft_item_score": float(weights["placement"]) / 2,
            "stability_score": float(weights["stability"]),
        },
        gate=TaskGate(metric=GATE_METRIC, minimum=threshold, kept_metrics=("fill_score",)),
    )


def rows_from(path: Path, candidate_id: str) -> list[TaskScore]:
    document = json.loads(path.read_text(encoding="utf-8"))
    rows: list[TaskScore] = []
    for task_id, record in document["per_task"].items():
        evaluation = record.get("evaluation")
        if not evaluation:
            # A task with no evaluation is a task that was never measured. Storing a zero here would
            # be storing a score the run never produced.
            continue
        rows.append(TaskScore(candidate_id, task_id, _raw_vector(evaluation)))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True, help="directory of scored run JSON files")
    parser.add_argument("--out", type=Path, required=True, help="destination JSONL score store")
    parser.add_argument("--spec-out", type=Path, help="write the scoring specification here (default: next to --out)")
    parser.add_argument("--verify", action="store_true", help="check derived composites against each run's own")
    parser.add_argument("--tolerance", type=float, default=0.01)
    arguments = parser.parse_args()

    files = sorted(path for path in arguments.results.glob("*.json"))
    if not files:
        raise SystemExit(f"no run files under {arguments.results}")

    if arguments.out.exists():
        arguments.out.unlink()  # the store is append-only; a re-import starts a new one
    store = TaskScoreStore(arguments.out)
    specs: dict[str, CompositeSpec] = {}
    reported: dict[str, float] = {}
    for path in files:
        candidate = path.stem
        document = json.loads(path.read_text(encoding="utf-8"))
        rows = rows_from(path, candidate)
        if not rows:
            continue
        store.append(rows)
        specs[candidate] = composite_spec(document)
        reported[candidate] = float(document["summary"]["composite_score"])

    distinct = {json.dumps(spec.to_dict(), sort_keys=True) for spec in specs.values()}
    if len(distinct) > 1:
        raise SystemExit(
            "these runs were scored under different specifications; compare only runs that share one:\n"
            + "\n".join(sorted(distinct))
        )
    spec = next(iter(specs.values()))
    spec_path = arguments.spec_out or arguments.out.with_suffix(".spec.json")
    spec_path.write_text(json.dumps(spec.to_dict(), indent=2) + "\n", encoding="utf-8")

    summary: dict[str, Any] = {
        "runs": len(specs),
        "rows": len(store.load()),
        "tasks": len(store.tasks()),
        "store": str(arguments.out),
        "spec": str(spec_path),
    }
    if arguments.verify:
        derived = composite_scores(tuple(store.latest().values()), spec)
        differences = {
            candidate: round(derived[candidate] - reported[candidate], 4)
            for candidate in sorted(reported)
            if abs(derived[candidate] - reported[candidate]) > arguments.tolerance
        }
        summary["verified"] = not differences
        summary["largest_difference"] = round(
            max((abs(derived[name] - reported[name]) for name in reported), default=0.0), 5
        )
        if differences:
            summary["differences"] = differences
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("verified", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
