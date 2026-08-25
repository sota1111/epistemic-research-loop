from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from epistemic_loop.benchmark.gold_findings import GoldFinding, concept_match
from epistemic_loop.benchmark.protocol import BenchmarkPlan
from epistemic_loop.benchmark.synthetic.scenarios import SCENARIOS
from epistemic_loop.holdout.sealed_store import SealedScoreStore

#: Regret the epistemic arm must remove per extra CPU-hour before the overhead counts as paid for.
EFFICIENCY_EPSILON = 1e-9


def discovery_score(text: str | None, findings: tuple[GoldFinding, ...]) -> tuple[float, list[str]]:
    """Weighted share of a scenario's planted structure that a run actually named.

    A scenario with no gold findings — the negative control — scores 0 for every system, which is the
    point: there is nothing there to find, so nothing can be credited for finding it.
    """
    if not findings:
        return 0.0, []
    matched = [finding for finding in findings if text and concept_match(text, finding)]
    total_weight = sum(finding.weight for finding in findings)
    return sum(finding.weight for finding in matched) / total_weight, [finding.id for finding in matched]


def finalize_benchmark(
    plan: BenchmarkPlan,
    output_root: str | Path,
    *,
    unseal_token: str,
) -> dict[str, Any]:
    """Unseal the paired runs and score them on more than the private number.

    A system that reaches the same private score by grinding a misleading split has not done the
    same work as one that found the structure. The report therefore carries four axes per pair:
    sealed regret, the CV-private gap the run's own numbers would have implied, compute spent, and
    which of the scenario's planted findings the run actually named.
    """
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
        gold = SCENARIOS[scenario].gold_findings if scenario in SCENARIOS else ()
        negative_control = bool(scenario in SCENARIOS and SCENARIOS[scenario].negative_control)
        pairs = []
        for replicate, systems in sorted(replicates.items()):
            if set(systems) != set(plan.systems):
                raise ValueError(f"unpaired run: {scenario}/{replicate}")
            a = systems["exploiter_only"]
            b = systems["epistemic"]
            won = b["sealed_regret"] < a["sealed_regret"]
            total_wins += int(won)
            total_pairs += 1
            extra_cpu = b["cpu_hours"] - a["cpu_hours"]
            regret_removed = a["sealed_regret"] - b["sealed_regret"]
            a_discovery, a_found = discovery_score(a["discovered_finding"], gold)
            b_discovery, b_found = discovery_score(b["discovered_finding"], gold)
            pairs.append(
                {
                    "replicate": replicate,
                    "seed": a["seed"],
                    "exploiter_regret": a["sealed_regret"],
                    "epistemic_regret": b["sealed_regret"],
                    "epistemic_won": won,
                    "compute_overhead": b["cpu_hours"] / a["cpu_hours"] - 1,
                    # The gap the run's own local numbers would have led it to believe.
                    "exploiter_cv_private_gap": a["cv_score"] - a["sealed_private_score"],
                    "epistemic_cv_private_gap": b["cv_score"] - b["sealed_private_score"],
                    "exploiter_discovery": a_discovery,
                    "epistemic_discovery": b_discovery,
                    "exploiter_findings": a_found,
                    "epistemic_findings": b_found,
                    "regret_removed_per_extra_cpu_hour": (
                        regret_removed / extra_cpu if extra_cpu > EFFICIENCY_EPSILON else None
                    ),
                }
            )
        scenarios[scenario] = {
            "negative_control": negative_control,
            "gold_findings": [finding.id for finding in gold],
            "pairs": pairs,
            "pairwise_win_rate": mean(float(item["epistemic_won"]) for item in pairs),
            "mean_exploiter_regret": mean(item["exploiter_regret"] for item in pairs),
            "mean_epistemic_regret": mean(item["epistemic_regret"] for item in pairs),
            "mean_compute_overhead": mean(item["compute_overhead"] for item in pairs),
            "mean_exploiter_cv_private_gap": mean(item["exploiter_cv_private_gap"] for item in pairs),
            "mean_epistemic_cv_private_gap": mean(item["epistemic_cv_private_gap"] for item in pairs),
            "exploiter_discovery_rate": mean(item["exploiter_discovery"] for item in pairs),
            "epistemic_discovery_rate": mean(item["epistemic_discovery"] for item in pairs),
        }
    discovery_scenarios = [item for item in scenarios.values() if item["gold_findings"]]
    controls = [item for item in scenarios.values() if item["negative_control"]]
    return {
        "benchmark_id": plan.benchmark_id,
        "complete": True,
        "paired_runs": total_pairs,
        "overall_pairwise_win_rate": total_wins / total_pairs,
        "holdout_violations": 0,
        # The headline claim is discovery, not rank: how much of the planted structure each arm named.
        "overall_epistemic_discovery_rate": (
            mean(item["epistemic_discovery_rate"] for item in discovery_scenarios) if discovery_scenarios else 0.0
        ),
        "overall_exploiter_discovery_rate": (
            mean(item["exploiter_discovery_rate"] for item in discovery_scenarios) if discovery_scenarios else 0.0
        ),
        # A research system that also wins the negative control is measuring something other than research.
        "negative_control_overhead": (mean(item["mean_compute_overhead"] for item in controls) if controls else 0.0),
        "negative_control_win_rate": (mean(item["pairwise_win_rate"] for item in controls) if controls else 0.0),
        "scenarios": scenarios,
    }
