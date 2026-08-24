from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

from epistemic_loop.benchmark.protocol import BenchmarkPlan
from epistemic_loop.benchmark.synthetic.scenarios import SCENARIOS, SyntheticAction, SyntheticScenario
from epistemic_loop.holdout.sealed_store import SealedScoreStore


@dataclass(frozen=True)
class SyntheticRunResult:
    benchmark_id: str
    scenario: str
    system: str
    replicate: int
    seed: int
    selected_action: str
    cpu_hours: float
    information_gain: float
    discovered_finding: str | None
    cv_score: float
    sealed_regret: float
    sealed_private_score: float


def _choose(scenario: SyntheticScenario, system: str) -> SyntheticAction:
    if system == "exploiter_only":
        return max(scenario.actions, key=lambda item: item.expected_gain / item.cost)
    if scenario.negative_control:
        # Cheap structural check then early exploitation; the final action remains ordinary HPO.
        return max(scenario.actions, key=lambda item: item.expected_gain / item.cost)
    return max(
        scenario.actions,
        key=lambda item: (
            0.20 * item.expected_gain
            + 0.45 * item.information
            + 0.20 * item.robustness
            + 0.15 * item.diversity
            - 0.15 * item.cost
        ),
    )


def run_synthetic_plan(
    plan: BenchmarkPlan,
    output_root: str | Path,
    *,
    unseal_token: str,
) -> list[Path]:
    output = Path(output_root)
    output.mkdir(parents=True, exist_ok=True)
    sealed_store = SealedScoreStore(output / "sealed")
    written: list[Path] = []
    for scenario_name in plan.scenarios:
        scenario = SCENARIOS[scenario_name]
        for replicate in range(plan.replicates):
            seed = plan.seeds[replicate]
            for system in plan.systems:
                action = _choose(scenario, system)
                noise = random.Random(seed).uniform(-0.005, 0.005)
                overhead = 1.2 if system == "epistemic" and scenario.negative_control else 1.0
                result = SyntheticRunResult(
                    benchmark_id=plan.benchmark_id,
                    scenario=scenario_name,
                    system=system,
                    replicate=replicate,
                    seed=seed,
                    selected_action=action.name,
                    cpu_hours=action.cost * overhead,
                    information_gain=action.information,
                    # Discovery is read off the action either system chose, not granted by label:
                    # crediting only the epistemic arm would decide the comparison in advance.
                    discovered_finding=action.finding,
                    cv_score=action.cv_score,
                    sealed_regret=max(0.0, action.sealed_regret + noise),
                    sealed_private_score=action.private_score,
                )
                public = asdict(result)
                sealed = {
                    "sealed_regret": public.pop("sealed_regret"),
                    "sealed_private_score": public.pop("sealed_private_score"),
                }
                result_path = output / "runs" / scenario_name / f"{replicate}-{system}.json"
                result_path.parent.mkdir(parents=True, exist_ok=True)
                result_path.write_text(json.dumps(public, indent=2, sort_keys=True), encoding="utf-8")
                score_id = f"{scenario_name}-{replicate}-{system}"
                sealed_store.seal(score_id, sealed, unseal_token)
                written.append(result_path)
    return written
