from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SyntheticAction:
    name: str
    lineage: str
    expected_gain: float
    information: float
    robustness: float
    diversity: float
    cost: float
    sealed_regret: float
    finding: str | None = None


@dataclass(frozen=True)
class SyntheticScenario:
    name: str
    actions: tuple[SyntheticAction, ...]
    negative_control: bool = False


SCENARIOS: dict[str, SyntheticScenario] = {
    "temporal_shift": SyntheticScenario(
        "temporal_shift",
        (
            SyntheticAction("random_cv_hpo", "gbdt", 0.90, 0.05, 0.10, 0.10, 1.0, 0.30),
            SyntheticAction(
                "compare_random_temporal_cv", "validation", 0.10, 0.95, 0.90, 0.95, 0.8, 0.04, "temporal validation"
            ),
            SyntheticAction("seed_ensemble", "ensemble", 0.55, 0.10, 0.70, 0.60, 1.2, 0.22),
        ),
    ),
    "spurious_leakage": SyntheticScenario(
        "spurious_leakage",
        (
            SyntheticAction("optimize_leaky_feature", "gbdt", 0.95, 0.02, 0.05, 0.10, 0.8, 0.36),
            SyntheticAction("ablate_suspect_feature", "leakage", 0.05, 0.98, 0.95, 0.95, 0.6, 0.03, "spurious leakage"),
            SyntheticAction("model_family_search", "model", 0.60, 0.15, 0.40, 0.70, 1.1, 0.25),
        ),
    ),
    "candidate_generation_bottleneck": SyntheticScenario(
        "candidate_generation_bottleneck",
        (
            SyntheticAction("ranker_hpo", "ranker", 0.85, 0.08, 0.30, 0.10, 1.0, 0.28),
            SyntheticAction(
                "candidate_recall_diagnostic",
                "candidate",
                0.20,
                0.90,
                0.80,
                0.90,
                0.9,
                0.05,
                "candidate generation bottleneck",
            ),
            SyntheticAction("ranker_ensemble", "ensemble", 0.55, 0.10, 0.55, 0.60, 1.2, 0.20),
        ),
    ),
    "iid_easy": SyntheticScenario(
        "iid_easy",
        (
            SyntheticAction("ordinary_hpo", "gbdt", 0.90, 0.05, 0.70, 0.20, 1.0, 0.02),
            SyntheticAction("iid_diagnostic", "validation", 0.10, 0.50, 0.70, 0.80, 0.20, 0.025, "iid structure"),
            SyntheticAction("seed_replication", "replication", 0.45, 0.20, 0.95, 0.50, 0.4, 0.022),
        ),
        negative_control=True,
    ),
}
