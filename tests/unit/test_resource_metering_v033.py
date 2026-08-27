from __future__ import annotations

from pathlib import Path

import pytest

from epistemic_loop.controller.resource_metering import (
    FIXED_THREAD_ENVIRONMENT,
    ArmBudgetState,
    ArmHardBudget,
    CgroupV2Meter,
    CgroupV2Snapshot,
    ObservedBudgetMatch,
    ResourceObservation,
    ResourceReservation,
    fixed_thread_environment,
)
from epistemic_loop.evaluation.v032 import SystemArm


def _write_cgroup(path: Path, *, usage: int, current: int = 100, peak: int = 200) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "cpu.stat").write_text(
        f"usage_usec {usage}\nuser_usec {usage - 10}\nsystem_usec 10\nnr_periods 1\n",
        encoding="utf-8",
    )
    (path / "memory.current").write_text(str(current), encoding="utf-8")
    (path / "memory.peak").write_text(str(peak), encoding="utf-8")


def test_cgroup_v2_meter_reads_process_tree_counters(tmp_path: Path) -> None:
    _write_cgroup(tmp_path, usage=1_000_000)
    meter = CgroupV2Meter(tmp_path)
    before = meter.snapshot(measured_at=10)
    _write_cgroup(tmp_path, usage=1_250_000, current=120, peak=240)
    after = meter.snapshot(measured_at=10.5)

    delta = after.delta(before)

    assert delta.process_tree_cpu_seconds == pytest.approx(0.25)
    assert delta.wall_clock_seconds == pytest.approx(0.5)
    assert delta.memory_peak_bytes == 240


def test_current_process_detection_marks_root_cgroup_unisolated(tmp_path: Path) -> None:
    _write_cgroup(tmp_path, usage=100)
    proc = tmp_path / "proc-cgroup"
    proc.write_text("0::/\n", encoding="utf-8")

    meter = CgroupV2Meter.for_current_process(mount=tmp_path, proc_cgroup=proc)

    assert meter.path == tmp_path
    assert meter.isolated is False


def test_snapshot_rejects_backwards_counters() -> None:
    later = CgroupV2Snapshot(1, 1, 0, 1, 1, 2)
    earlier = CgroupV2Snapshot(2, 2, 0, 1, 1, 1)
    with pytest.raises(ValueError, match="backwards"):
        later.delta(earlier)


def _budget() -> ArmHardBudget:
    return ArmHardBudget(100, 1_000, 200, 20, 100, 30)


def _observation(cpu: float = 10, wall: float = 20) -> ResourceObservation:
    return ResourceObservation(cpu, cpu * 0.8, cpu * 0.2, wall, 100, 200)


def test_hard_budget_refuses_work_that_spends_finalization_reserve() -> None:
    state = ArmBudgetState(SystemArm.C, _budget(), used_process_tree_cpu_seconds=75)
    decision = state.admit(ResourceReservation(10, 1, 1))
    finalization = state.admit(ResourceReservation(10, 1, 1), finalization=True)

    assert not decision.admitted
    assert decision.reasons == ("process_tree_cpu_budget",)
    assert finalization.admitted


def test_observed_resource_and_opportunity_cost_accounting() -> None:
    state = ArmBudgetState(SystemArm.C, _budget())
    state.record(_observation(6), tokens=20, work_type="structure_maturation", avoided_invalid_decision=True)
    state.record(_observation(4), tokens=10, work_type="candidate")

    assert state.used_process_tree_cpu_seconds == 10
    assert state.used_tokens == 30
    assert state.avoided_invalid_decisions == 1
    assert state.opportunity_cost_cpu_fraction == pytest.approx(0.6)
    with pytest.raises(ValueError, match="work_type"):
        state.record(_observation(), tokens=0, work_type="diagnostic")


def test_observed_budget_match_uses_actual_cpu_token_and_wall() -> None:
    states = tuple(ArmBudgetState(arm, _budget()) for arm in SystemArm)
    for state in states:
        state.record(_observation(), tokens=100, work_type="candidate")
    assert ObservedBudgetMatch.assess(states).matched
    states[1].used_process_tree_cpu_seconds = 20
    assert ObservedBudgetMatch.assess(states).mismatches == ("used_process_tree_cpu_seconds",)


def test_fixed_thread_environment_overrides_existing_values() -> None:
    environment = fixed_thread_environment({"OMP_NUM_THREADS": "99", "KEEP": "yes"})
    assert all(environment[key] == "2" for key in FIXED_THREAD_ENVIRONMENT)
    assert environment["KEEP"] == "yes"
