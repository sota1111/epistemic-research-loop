from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_benchmark_report(result: dict[str, Any]) -> str:
    lines = [
        f"# Benchmark {result['benchmark_id']}",
        "",
        f"- Paired runs: {result['paired_runs']}",
        f"- Overall epistemic win rate: {result['overall_pairwise_win_rate']:.1%}",
        f"- Discovery rate (epistemic vs exploiter): "
        f"{result.get('overall_epistemic_discovery_rate', 0.0):.1%} vs "
        f"{result.get('overall_exploiter_discovery_rate', 0.0):.1%}",
        f"- Negative control: {result.get('negative_control_win_rate', 0.0):.1%} win rate at "
        f"{result.get('negative_control_overhead', 0.0):.1%} compute overhead",
        f"- Holdout violations: {result['holdout_violations']}",
        "",
        "Discovery rate is the weighted share of each scenario's planted structure the arm named; the",
        "negative control is an ordinary IID problem where research is supposed to earn nothing.",
        "",
        "## Scenario results",
        "",
        "| Scenario | A regret | B regret | B win rate | Compute overhead | A CV-private gap | "
        "B CV-private gap | A discovery | B discovery |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, scenario in sorted(result["scenarios"].items()):
        lines.append(
            f"| {name} | {scenario['mean_exploiter_regret']:.4f} | "
            f"{scenario['mean_epistemic_regret']:.4f} | {scenario['pairwise_win_rate']:.1%} | "
            f"{scenario['mean_compute_overhead']:.1%} | "
            f"{scenario.get('mean_exploiter_cv_private_gap', 0.0):.4f} | "
            f"{scenario.get('mean_epistemic_cv_private_gap', 0.0):.4f} | "
            f"{scenario.get('exploiter_discovery_rate', 0.0):.1%} | "
            f"{scenario.get('epistemic_discovery_rate', 0.0):.1%} |"
        )
    lines.extend(["", "## Full paired result", "", "```json", json.dumps(result, indent=2, sort_keys=True), "```"])
    systems = result.get("systems", [])
    if len(systems) > 2:
        lines.extend(
            [
                "",
                "## A/B/B+/C system summary",
                "",
                "| Scenario | System | Mean regret | Mean private score | Mean CPU hours |",
                "| --- | --- | ---: | ---: | ---: |",
            ]
        )
        for scenario_name, scenario in sorted(result["scenarios"].items()):
            for system in systems:
                summary = scenario["systems"][system]
                lines.append(
                    f"| {scenario_name} | {system} | {summary['mean_regret']:.4f} | "
                    f"{summary['mean_private_score']:.4f} | {summary['mean_cpu_hours']:.2f} |"
                )
    return "\n".join(lines) + "\n"


def write_benchmark_report(result: dict[str, Any], destination: str | Path) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_benchmark_report(result), encoding="utf-8")
    return path
