from __future__ import annotations

from dataclasses import dataclass

from epistemic_loop.benchmark.gold_findings import GoldFinding


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
    #: Local cross-validation score the action reports. Optimistic where the split is misleading.
    cv_score: float = 0.0
    #: Sealed private score the action actually earns; the CV-private gap is the difference.
    private_score: float = 0.0


@dataclass(frozen=True)
class SyntheticScenario:
    name: str
    actions: tuple[SyntheticAction, ...]
    negative_control: bool = False
    #: The structure a research system is supposed to discover here; empty for a negative control.
    gold_findings: tuple[GoldFinding, ...] = ()


SCENARIOS: dict[str, SyntheticScenario] = {
    "temporal_shift": SyntheticScenario(
        "temporal_shift",
        (
            # Random k-fold looks excellent and transfers badly: the CV-private gap is the tell.
            SyntheticAction(
                "random_cv_hpo", "gbdt", 0.90, 0.05, 0.10, 0.10, 1.0, 0.30, None, cv_score=0.880, private_score=0.700
            ),
            SyntheticAction(
                "compare_random_temporal_cv",
                "validation",
                0.10,
                0.95,
                0.90,
                0.95,
                0.8,
                0.04,
                "temporal validation",
                cv_score=0.965,
                private_score=0.960,
            ),
            SyntheticAction(
                "seed_ensemble",
                "ensemble",
                0.55,
                0.10,
                0.70,
                0.60,
                1.2,
                0.22,
                None,
                cv_score=0.870,
                private_score=0.780,
            ),
        ),
        gold_findings=(
            GoldFinding(
                id="temporal-shift-validation",
                category="validation",
                concept="the evaluation split is time-ordered, so random k-fold overstates the score",
                acceptable_discovery_patterns=["temporal validation", "time-ordered split", "temporal cv"],
                weight=3,
            ),
        ),
    ),
    "spurious_leakage": SyntheticScenario(
        "spurious_leakage",
        (
            SyntheticAction(
                "optimize_leaky_feature",
                "gbdt",
                0.95,
                0.02,
                0.05,
                0.10,
                0.8,
                0.36,
                None,
                cv_score=0.940,
                private_score=0.640,
            ),
            SyntheticAction(
                "ablate_suspect_feature",
                "leakage",
                0.05,
                0.98,
                0.95,
                0.95,
                0.6,
                0.03,
                "spurious leakage",
                cv_score=0.975,
                private_score=0.970,
            ),
            SyntheticAction(
                "model_family_search",
                "model",
                0.60,
                0.15,
                0.40,
                0.70,
                1.1,
                0.25,
                None,
                cv_score=0.900,
                private_score=0.750,
            ),
        ),
        gold_findings=(
            GoldFinding(
                id="spurious-feature",
                category="leakage",
                concept="one feature is target-derived and does not exist at inference time",
                acceptable_discovery_patterns=["spurious leakage", "leaky feature", "target-derived"],
                weight=3,
            ),
        ),
    ),
    "candidate_generation_bottleneck": SyntheticScenario(
        "candidate_generation_bottleneck",
        (
            SyntheticAction(
                "ranker_hpo", "ranker", 0.85, 0.08, 0.30, 0.10, 1.0, 0.28, None, cv_score=0.720, private_score=0.680
            ),
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
                cv_score=0.955,
                private_score=0.950,
            ),
            SyntheticAction(
                "ranker_ensemble",
                "ensemble",
                0.55,
                0.10,
                0.55,
                0.60,
                1.2,
                0.20,
                None,
                cv_score=0.800,
                private_score=0.760,
            ),
        ),
        gold_findings=(
            GoldFinding(
                id="recall-ceiling",
                category="search_space",
                concept="the ranker cannot exceed the recall of the candidate generator feeding it",
                acceptable_discovery_patterns=["candidate generation bottleneck", "recall ceiling", "candidate recall"],
                weight=3,
            ),
        ),
    ),
    # Negative control: an ordinary IID problem where research earns nothing and costs 20% more.
    "iid_easy": SyntheticScenario(
        "iid_easy",
        (
            SyntheticAction(
                "ordinary_hpo", "gbdt", 0.90, 0.05, 0.70, 0.20, 1.0, 0.02, None, cv_score=0.910, private_score=0.905
            ),
            SyntheticAction(
                "iid_diagnostic",
                "validation",
                0.10,
                0.50,
                0.70,
                0.80,
                0.20,
                0.025,
                "iid structure",
                cv_score=0.906,
                private_score=0.902,
            ),
            SyntheticAction(
                "seed_replication",
                "replication",
                0.45,
                0.20,
                0.95,
                0.50,
                0.4,
                0.022,
                None,
                cv_score=0.908,
                private_score=0.904,
            ),
        ),
        negative_control=True,
    ),
}
