from typer.testing import CliRunner

from epistemic_loop.benchmark.protocol import BenchmarkPlan, save_plan
from epistemic_loop.cli import app


def test_benchmark_rejects_short_token_before_writing_output(tmp_path) -> None:
    plan_path = tmp_path / "plan.yaml"
    output_root = tmp_path / "output"
    save_plan(
        BenchmarkPlan(
            benchmark_id="token-check",
            scenarios=["iid_easy"],
            replicates=3,
            seeds=[1, 2, 3],
            budgets={"max_experiments": 3},
        ),
        plan_path,
    )

    result = CliRunner().invoke(
        app,
        ["benchmark", "run", "--plan", str(plan_path), "--output-root", str(output_root)],
        env={"BENCHMARK_UNSEAL_TOKEN": "too-short"},
    )

    assert result.exit_code == 2
    assert "at least 16 characters" in result.output
    assert not output_root.exists()
