from __future__ import annotations

import json
import os
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from epistemic_loop.domain.models import ResourceEstimate


class ResourceUnavailable(RuntimeError):
    """The proposal is valid but must remain queued until capacity is released."""


@dataclass(frozen=True)
class SchedulerDecision:
    accepted: bool
    reason: str
    heavy: bool


class ResourceScheduler:
    """Atomic memory-aware admission control for isolated experiment workers."""

    def __init__(
        self,
        *,
        total_memory_gb: float | None = None,
        total_gpu_memory_gb: float = 0,
        total_cpu_cores: int | None = None,
        max_concurrent_heavy_experiments: int = 1,
        max_concurrent_light_experiments: int = 3,
        max_concurrent_parquet_full_scans: int = 1,
        memory_safety_margin: float = 0.25,
        state_path: str | Path | None = None,
    ):
        if not 0 <= memory_safety_margin < 1:
            raise ValueError("memory_safety_margin must be in [0, 1)")
        self.total_memory_gb = total_memory_gb or _physical_memory_gb()
        self.total_gpu_memory_gb = total_gpu_memory_gb
        self.total_cpu_cores = total_cpu_cores or max(1, os.cpu_count() or 1)
        self.max_heavy = max_concurrent_heavy_experiments
        self.max_light = max_concurrent_light_experiments
        self.max_full_scans = max_concurrent_parquet_full_scans
        self.memory_safety_margin = memory_safety_margin
        self.state_path = Path(state_path) if state_path is not None else None
        if self.state_path is not None:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
        if min(self.total_memory_gb, self.total_cpu_cores, self.max_heavy, self.max_light, self.max_full_scans) <= 0:
            raise ValueError("scheduler capacities must be positive")
        self._running: dict[str, ResourceEstimate] = {}
        self._lock = threading.Lock()

    @property
    def usable_memory_gb(self) -> float:
        return self.total_memory_gb * (1 - self.memory_safety_margin)

    def pressure(self) -> dict[str, float]:
        if self.state_path is not None:
            with self._file_state() as state:
                running = self._estimates_from_state(state)
                return self._pressure(running)
        with self._lock:
            return self._pressure(list(self._running.values()))

    def can_schedule(self, estimate: ResourceEstimate) -> SchedulerDecision:
        if self.state_path is not None:
            with self._file_state() as state:
                return self._decision(estimate, self._estimates_from_state(state))
        with self._lock:
            return self._decision(estimate)

    def reserve(self, estimate: ResourceEstimate) -> str:
        if self.state_path is not None:
            with self._file_state() as state:
                decision = self._decision(estimate, self._estimates_from_state(state))
                if not decision.accepted:
                    raise ResourceUnavailable(decision.reason)
                token = f"reservation-{uuid.uuid4().hex}"
                state[token] = {"pid": os.getpid(), "estimate": estimate.model_dump(mode="json")}
                return token
        with self._lock:
            decision = self._decision(estimate)
            if not decision.accepted:
                raise ResourceUnavailable(decision.reason)
            token = f"reservation-{uuid.uuid4().hex}"
            self._running[token] = estimate
            return token

    def release(self, token: str) -> None:
        if self.state_path is not None:
            with self._file_state() as state:
                if token not in state:
                    raise KeyError(f"unknown scheduler reservation: {token}")
                state.pop(token)
                return
        with self._lock:
            if token not in self._running:
                raise KeyError(f"unknown scheduler reservation: {token}")
            self._running.pop(token)

    @contextmanager
    def reservation(self, estimate: ResourceEstimate) -> Iterator[None]:
        token = self.reserve(estimate)
        try:
            yield
        finally:
            self.release(token)

    def _decision(
        self,
        estimate: ResourceEstimate,
        running: list[ResourceEstimate] | None = None,
    ) -> SchedulerDecision:
        running = list(self._running.values()) if running is None else running
        heavy_count = sum(item.is_heavy for item in running)
        light_count = sum(not item.is_heavy for item in running)
        if estimate.memory_gb + sum(item.memory_gb for item in running) > self.usable_memory_gb:
            return SchedulerDecision(False, "memory safety margin would be exceeded", estimate.is_heavy)
        if estimate.cpu_cores + sum(item.cpu_cores for item in running) > self.total_cpu_cores:
            return SchedulerDecision(False, "CPU capacity would be exceeded", estimate.is_heavy)
        if estimate.gpu_memory_gb + sum(item.gpu_memory_gb for item in running) > self.total_gpu_memory_gb:
            return SchedulerDecision(False, "GPU memory capacity would be exceeded", estimate.is_heavy)
        if estimate.is_heavy and heavy_count >= self.max_heavy:
            return SchedulerDecision(False, "heavy experiment concurrency limit reached", True)
        if not estimate.is_heavy and light_count >= self.max_light:
            return SchedulerDecision(False, "light experiment concurrency limit reached", False)
        full_scans = sum(item.full_table_materialization for item in running)
        if estimate.full_table_materialization and full_scans >= self.max_full_scans:
            return SchedulerDecision(False, "Parquet full-scan concurrency limit reached", estimate.is_heavy)
        return SchedulerDecision(True, "capacity reserved", estimate.is_heavy)

    def _pressure(self, running: list[ResourceEstimate]) -> dict[str, float]:
        memory = sum(item.memory_gb for item in running)
        gpu = sum(item.gpu_memory_gb for item in running)
        cpu = sum(item.cpu_cores for item in running)
        return {
            "memory": memory / self.usable_memory_gb,
            "gpu_memory": gpu / self.total_gpu_memory_gb if self.total_gpu_memory_gb else float(gpu > 0),
            "cpu": cpu / self.total_cpu_cores,
            "running": float(len(running)),
        }

    @contextmanager
    def _file_state(self) -> Iterator[dict[str, object]]:
        if self.state_path is None:  # pragma: no cover - guarded by callers
            raise RuntimeError("file state was not configured")
        import fcntl

        lock_path = self.state_path.with_suffix(self.state_path.suffix + ".lock")
        with lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                try:
                    raw = json.loads(self.state_path.read_text(encoding="utf-8")) if self.state_path.exists() else {}
                except json.JSONDecodeError:
                    raw = {}
                state = raw if isinstance(raw, dict) else {}
                self._remove_stale(state)
                yield state
                temporary = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
                temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                temporary.replace(self.state_path)
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _remove_stale(state: dict[str, object]) -> None:
        for token, raw in list(state.items()):
            pid = raw.get("pid") if isinstance(raw, dict) else None
            if not isinstance(pid, int) or not _process_alive(pid):
                state.pop(token)

    @staticmethod
    def _estimates_from_state(state: dict[str, object]) -> list[ResourceEstimate]:
        return [
            ResourceEstimate.model_validate(raw["estimate"])
            for raw in state.values()
            if isinstance(raw, dict) and isinstance(raw.get("estimate"), dict)
        ]


def _physical_memory_gb() -> float:
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024**3
    except (ValueError, OSError, AttributeError):
        return 4.0


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
