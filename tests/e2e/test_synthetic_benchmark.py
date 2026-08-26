from epistemic_loop.benchmark.evaluator import finalize_benchmark
from epistemic_loop.benchmark.paired_runner import run_synthetic_plan
from epistemic_loop.benchmark.protocol import BenchmarkPlan


def test_epistemic_system_wins_structure_benchmarks_and_keeps_iid_overhead_bounded(tmp_path) -> None:
    plan = BenchmarkPlan(
        benchmark_id="test-ab",
        scenarios=["temporal_shift", "spurious_leakage", "candidate_generation_bottleneck", "iid_easy"],
        replicates=3,
        seeds=[101, 118, 135],
        budgets={"max_experiments": 40},
    )
    token = "evaluator-only-secret-token"
    run_synthetic_plan(plan, tmp_path, unseal_token=token)
    result = finalize_benchmark(plan, tmp_path, unseal_token=token)
    structure_wins = sum(
        result["scenarios"][name]["pairwise_win_rate"] == 1
        for name in ("temporal_shift", "spurious_leakage", "candidate_generation_bottleneck")
    )
    assert structure_wins >= 2
    assert result["scenarios"]["iid_easy"]["mean_compute_overhead"] <= 0.30
    assert result["holdout_violations"] == 0


def test_the_benchmark_scores_discovery_and_the_cv_private_gap_not_only_rank(tmp_path) -> None:
    """Winning on the private score is not the claim; naming the planted structure is.

    Both arms are credited for whatever finding the action they picked exposes, so the discovery
    gap below is a result of what each system chose to run, not of how the runs were labelled.
    """
    plan = BenchmarkPlan(
        benchmark_id="test-discovery",
        scenarios=["temporal_shift", "spurious_leakage", "candidate_generation_bottleneck", "iid_easy"],
        replicates=3,
        seeds=[101, 118, 135],
        budgets={"max_experiments": 40},
    )
    token = "evaluator-only-secret-token"
    run_synthetic_plan(plan, tmp_path, unseal_token=token)
    result = finalize_benchmark(plan, tmp_path, unseal_token=token)

    assert result["overall_epistemic_discovery_rate"] > result["overall_exploiter_discovery_rate"]

    shift = result["scenarios"]["temporal_shift"]
    assert shift["epistemic_discovery_rate"] == 1.0
    assert shift["exploiter_discovery_rate"] == 0.0
    # The exploiter's own local numbers would have told it a much better story than the truth.
    assert shift["mean_exploiter_cv_private_gap"] > shift["mean_epistemic_cv_private_gap"]

    control = result["scenarios"]["iid_easy"]
    assert control["negative_control"] is True
    assert control["gold_findings"] == [], "a negative control has no structure to find"
    assert control["epistemic_discovery_rate"] == 0.0
    assert result["negative_control_win_rate"] == 0.0, "research must not appear to help where it cannot"
    assert result["negative_control_overhead"] > 0, "and it must still be charged for trying"


def test_compute_efficiency_is_reported_where_research_cost_extra(tmp_path) -> None:
    plan = BenchmarkPlan(
        benchmark_id="test-efficiency",
        scenarios=["iid_easy"],
        replicates=3,
        seeds=[101, 118, 135],
        budgets={"max_experiments": 40},
    )
    token = "evaluator-only-secret-token"
    run_synthetic_plan(plan, tmp_path, unseal_token=token)
    result = finalize_benchmark(plan, tmp_path, unseal_token=token)

    pair = result["scenarios"]["iid_easy"]["pairs"][0]
    assert pair["regret_removed_per_extra_cpu_hour"] is not None
    assert pair["regret_removed_per_extra_cpu_hour"] <= 0, "the control buys nothing with its overhead"


def test_a_b_bplus_c_are_compared_in_one_matched_plan(tmp_path) -> None:
    plan = BenchmarkPlan(
        benchmark_id="test-four-arm",
        scenarios=["temporal_shift", "iid_easy"],
        replicates=3,
        seeds=[101, 118, 135],
        budgets={"max_experiments": 40, "max_cpu_hours": 120},
        systems=("system_a", "system_b", "system_b_plus", "system_c"),
    )
    token = "evaluator-only-secret-token"
    run_synthetic_plan(plan, tmp_path, unseal_token=token)
    result = finalize_benchmark(plan, tmp_path, unseal_token=token)

    assert result["systems"] == list(plan.systems)
    assert result["baseline_system"] == "system_a"
    assert result["epistemic_system"] == "system_c"
    assert set(result["scenarios"]["temporal_shift"]["systems"]) == set(plan.systems)
