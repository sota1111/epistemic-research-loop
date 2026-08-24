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
