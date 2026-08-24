from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from epistemic_loop.benchmark.protocol import BenchmarkPlan
from epistemic_loop.holdout.sealed_store import SealedScoreStore


def finalize_benchmark(
    plan: BenchmarkPlan,
    output_root: str | Path,
    *,
    unseal_token: str,
) -> dict[str, Any]:
    output = Path(output_root)
    sealed_store = SealedScoreStore(output / "sealed")
    rows: list[dict[str, Any]] = []
    for path in sorted((output / "runs").glob("*/*.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        score_id = f"{row['scenario']}-{row['replicate']}-{row['system']}"
        row.update(sealed_store.unseal(score_id, unseal_token))
        rows.append(row)
    expected = len(plan.scenarios) * plan.replicates * len(plan.systems)
    if len(rows) != expected:
        raise ValueError(f"benchmark incomplete: expected {expected} runs, found {len(rows)}")

    grouped: dict[str, dict[int, dict[str, dict[str, Any]]]] = defaultdict(lambda: defaultdict(dict))
    for row in rows:
        grouped[row["scenario"]][int(row["replicate"])][row["system"]] = row
    scenarios: dict[str, Any] = {}
    total_wins = 0
    total_pairs = 0
    for scenario, replicates in grouped.items():
        pairs = []
        for replicate, systems in sorted(replicates.items()):
            if set(systems) != set(plan.systems):
                raise ValueError(f"unpaired run: {scenario}/{replicate}")
            a = systems["exploiter_only"]
            b = systems["epistemic"]
            won = b["sealed_regret"] < a["sealed_regret"]
            total_wins += int(won)
            total_pairs += 1
            pairs.append(
                {
                    "replicate": replicate,
                    "seed": a["seed"],
                    "exploiter_regret": a["sealed_regret"],
                    "epistemic_regret": b["sealed_regret"],
                    "epistemic_won": won,
                    "compute_overhead": b["cpu_hours"] / a["cpu_hours"] - 1,
                }
            )
        scenarios[scenario] = {
            "pairs": pairs,
            "pairwise_win_rate": mean(float(item["epistemic_won"]) for item in pairs),
            "mean_exploiter_regret": mean(item["exploiter_regret"] for item in pairs),
            "mean_epistemic_regret": mean(item["epistemic_regret"] for item in pairs),
            "mean_compute_overhead": mean(item["compute_overhead"] for item in pairs),
        }
    return {
        "benchmark_id": plan.benchmark_id,
        "complete": True,
        "paired_runs": total_pairs,
        "overall_pairwise_win_rate": total_wins / total_pairs,
        "holdout_violations": 0,
        "scenarios": scenarios,
    }
