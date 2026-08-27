"""Observed cgroup-v2 resource accounting for v0.3.3 matched arms."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

from epistemic_loop.evaluation.v032 import SystemArm

FIXED_THREAD_ENVIRONMENT: dict[str, str] = {
    "OMP_NUM_THREADS": "2",
    "MKL_NUM_THREADS": "2",
    "OPENBLAS_NUM_THREADS": "2",
    "NUMEXPR_NUM_THREADS": "2",
}


@dataclass(frozen=True)
class CgroupV2Snapshot:
    cpu_usage_seconds: float
    cpu_user_seconds: float
    cpu_system_seconds: float
    memory_current_bytes: int
    memory_peak_bytes: int
    measured_at: float

    def delta(self, earlier: CgroupV2Snapshot) -> ResourceObservation:
        if self.measured_at < earlier.measured_at:
            raise ValueError("snapshots are not ordered")
        values = (
            self.cpu_usage_seconds - earlier.cpu_usage_seconds,
            self.cpu_user_seconds - earlier.cpu_user_seconds,
            self.cpu_system_seconds - earlier.cpu_system_seconds,
        )
        if any(item < 0 for item in values):
            raise ValueError("cgroup counters moved backwards")
        return ResourceObservation(
            process_tree_cpu_seconds=values[0],
            process_tree_user_seconds=values[1],
            process_tree_system_seconds=values[2],
            wall_clock_seconds=self.measured_at - earlier.measured_at,
            memory_current_bytes=self.memory_current_bytes,
            memory_peak_bytes=max(earlier.memory_peak_bytes, self.memory_peak_bytes),
        )


@dataclass(frozen=True)
class ResourceObservation:
    process_tree_cpu_seconds: float
    process_tree_user_seconds: float
    process_tree_system_seconds: float
    wall_clock_seconds: float
    memory_current_bytes: int
    memory_peak_bytes: int


class CgroupV2Meter:
    """Read cumulative resource counters from an isolated cgroup-v2 node."""

    def __init__(self, cgroup_path: str | Path, *, isolated: bool = True):
        self.path = Path(cgroup_path)
        self.isolated = isolated

    @classmethod
    def for_current_process(
        cls,
        *,
        mount: str | Path = "/sys/fs/cgroup",
        proc_cgroup: str | Path = "/proc/self/cgroup",
    ) -> CgroupV2Meter:
        line = Path(proc_cgroup).read_text(encoding="utf-8").strip().splitlines()
        unified = next((item.split("::", 1)[1] for item in line if "::" in item), None)
        if unified is None:
            raise RuntimeError("current process is not attached to a cgroup-v2 hierarchy")
        relative = unified.lstrip("/")
        return cls(Path(mount) / relative, isolated=unified != "/")

    def snapshot(self, *, measured_at: float | None = None) -> CgroupV2Snapshot:
        cpu = _parse_key_values((self.path / "cpu.stat").read_text(encoding="utf-8"))
        required = {"usage_usec", "user_usec", "system_usec"}
        if not required.issubset(cpu):
            raise ValueError("cpu.stat is missing cgroup-v2 CPU counters")
        return CgroupV2Snapshot(
            cpu_usage_seconds=cpu["usage_usec"] / 1_000_000,
            cpu_user_seconds=cpu["user_usec"] / 1_000_000,
            cpu_system_seconds=cpu["system_usec"] / 1_000_000,
            memory_current_bytes=_read_counter(self.path / "memory.current"),
            memory_peak_bytes=_read_counter(self.path / "memory.peak"),
            measured_at=time.monotonic() if measured_at is None else measured_at,
        )


def _parse_key_values(text: str) -> dict[str, int]:
    values: dict[str, int] = {}
    for line in text.splitlines():
        key, raw = line.split(maxsplit=1)
        if raw != "max":
            values[key] = int(raw)
    return values


def _read_counter(path: Path) -> int:
    value = path.read_text(encoding="utf-8").strip()
    if value == "max":
        return 0
    return int(value)


def fixed_thread_environment(base: dict[str, str] | None = None) -> dict[str, str]:
    environment = dict(os.environ if base is None else base)
    environment.update(FIXED_THREAD_ENVIRONMENT)
    return environment


@dataclass(frozen=True)
class ResourceReservation:
    process_tree_cpu_seconds: float
    token_count: int
    wall_clock_seconds: float


@dataclass(frozen=True)
class ArmHardBudget:
    process_tree_cpu_seconds: float
    token_count: int
    wall_clock_seconds: float
    finalization_cpu_reserve_seconds: float
    finalization_token_reserve: int
    finalization_wall_reserve_seconds: float

    def __post_init__(self) -> None:
        if (
            min(
                self.process_tree_cpu_seconds,
                self.token_count,
                self.wall_clock_seconds,
                self.finalization_cpu_reserve_seconds,
                self.finalization_token_reserve,
                self.finalization_wall_reserve_seconds,
            )
            < 0
        ):
            raise ValueError("budget values must be non-negative")
        if self.finalization_cpu_reserve_seconds > self.process_tree_cpu_seconds:
            raise ValueError("CPU finalization reserve exceeds budget")
        if self.finalization_token_reserve > self.token_count:
            raise ValueError("token finalization reserve exceeds budget")
        if self.finalization_wall_reserve_seconds > self.wall_clock_seconds:
            raise ValueError("wall finalization reserve exceeds budget")


@dataclass(frozen=True)
class AdmissionDecision:
    admitted: bool
    reasons: tuple[str, ...]


@dataclass
class ArmBudgetState:
    arm: SystemArm
    budget: ArmHardBudget
    used_process_tree_cpu_seconds: float = 0.0
    used_tokens: int = 0
    used_wall_clock_seconds: float = 0.0
    peak_memory_bytes: int = 0
    structure_maturation_cpu_seconds: float = 0.0
    candidate_cpu_seconds: float = 0.0
    avoided_invalid_decisions: int = 0

    def admit(self, reservation: ResourceReservation, *, finalization: bool = False) -> AdmissionDecision:
        cpu_reserve = 0.0 if finalization else self.budget.finalization_cpu_reserve_seconds
        token_reserve = 0 if finalization else self.budget.finalization_token_reserve
        wall_reserve = 0.0 if finalization else self.budget.finalization_wall_reserve_seconds
        checks = {
            "process_tree_cpu_budget": (
                self.used_process_tree_cpu_seconds + reservation.process_tree_cpu_seconds
                <= self.budget.process_tree_cpu_seconds - cpu_reserve
            ),
            "token_budget": self.used_tokens + reservation.token_count <= self.budget.token_count - token_reserve,
            "wall_clock_budget": (
                self.used_wall_clock_seconds + reservation.wall_clock_seconds
                <= self.budget.wall_clock_seconds - wall_reserve
            ),
        }
        reasons = tuple(name for name, passed in checks.items() if not passed)
        return AdmissionDecision(not reasons, reasons)

    def record(
        self,
        observation: ResourceObservation,
        *,
        tokens: int,
        work_type: str,
        avoided_invalid_decision: bool = False,
    ) -> None:
        if min(observation.process_tree_cpu_seconds, observation.wall_clock_seconds, tokens) < 0:
            raise ValueError("observed resource use must be non-negative")
        self.used_process_tree_cpu_seconds += observation.process_tree_cpu_seconds
        self.used_tokens += tokens
        self.used_wall_clock_seconds += observation.wall_clock_seconds
        self.peak_memory_bytes = max(self.peak_memory_bytes, observation.memory_peak_bytes)
        if work_type == "structure_maturation":
            self.structure_maturation_cpu_seconds += observation.process_tree_cpu_seconds
        elif work_type == "candidate":
            self.candidate_cpu_seconds += observation.process_tree_cpu_seconds
        else:
            raise ValueError("work_type must be candidate or structure_maturation")
        self.avoided_invalid_decisions += int(avoided_invalid_decision)

    @property
    def opportunity_cost_cpu_fraction(self) -> float:
        total = self.structure_maturation_cpu_seconds + self.candidate_cpu_seconds
        return self.structure_maturation_cpu_seconds / total if total else 0.0


@dataclass(frozen=True)
class ObservedBudgetMatch:
    matched: bool
    mismatches: tuple[str, ...]

    @classmethod
    def assess(
        cls,
        states: tuple[ArmBudgetState, ...],
        *,
        relative_tolerance: float = 0.01,
    ) -> ObservedBudgetMatch:
        if {state.arm for state in states} != {SystemArm.B, SystemArm.B_PLUS, SystemArm.C}:
            return cls(False, ("arms_must_be_exactly_B_B_plus_C",))
        fields = ("used_process_tree_cpu_seconds", "used_tokens", "used_wall_clock_seconds")
        mismatches: list[str] = []
        for field_name in fields:
            values = [float(getattr(state, field_name)) for state in states]
            scale = max(max(values), 1.0)
            if max(values) - min(values) > scale * relative_tolerance:
                mismatches.append(field_name)
        return cls(not mismatches, tuple(mismatches))
