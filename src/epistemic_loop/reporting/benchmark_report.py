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
        f"- Holdout violations: {result['holdout_violations']}",
        "",
        "## Scenario results",
        "",
        "| Scenario | A regret | B regret | B win rate | Compute overhead |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, scenario in sorted(result["scenarios"].items()):
        lines.append(
            f"| {name} | {scenario['mean_exploiter_regret']:.4f} | "
            f"{scenario['mean_epistemic_regret']:.4f} | {scenario['pairwise_win_rate']:.1%} | "
            f"{scenario['mean_compute_overhead']:.1%} |"
        )
    lines.extend(["", "## Full paired result", "", "```json", json.dumps(result, indent=2, sort_keys=True), "```"])
    return "\n".join(lines) + "\n"


def write_benchmark_report(result: dict[str, Any], destination: str | Path) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_benchmark_report(result), encoding="utf-8")
    return path
