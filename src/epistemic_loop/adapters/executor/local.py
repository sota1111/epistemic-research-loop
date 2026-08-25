from __future__ import annotations

import hashlib
import json
import os
import resource
import shlex
import shutil
import signal
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from epistemic_loop.adapters.executor.base import ExecutorAdapter
from epistemic_loop.domain.enums import FailureClass
from epistemic_loop.domain.models import ExperimentManifest, ExperimentRequest, ExperimentResult, ObservedResourceUsage


class LocalExecutor(ExecutorAdapter):
    """Development executor. Production should use the control-plane Docker sandbox."""

    def __init__(
        self,
        workspace: str | Path,
        result_root: str | Path,
        *,
        command_allowlist: tuple[str, ...] = ("python", "python3", "uv", "bash"),
    ):
        self.workspace = Path(workspace).resolve()
        self.result_root = Path(result_root).resolve()
        self.result_root.mkdir(parents=True, exist_ok=True)
        self.command_allowlist = command_allowlist

    def _result_path(self, request: ExperimentRequest) -> Path:
        return self.result_root / request.run_id / request.experiment_id / "result.json"

    def submit(self, request: ExperimentRequest) -> ExperimentResult:
        output_root = self._result_path(request).parent
        output_root.mkdir(parents=True, exist_ok=True)
        # The proposal is written before the output directory is known, so the command has to be
        # able to name it symbolically. Without this the only way to pass `--output` is to guess a
        # path, and an experiment that runs but writes somewhere else is scored as a failure.
        command = request.command.replace("${ERL_OUTPUT_DIR}", str(output_root)).replace(
            "$ERL_OUTPUT_DIR", str(output_root)
        )
        arguments = shlex.split(command)
        if not arguments or Path(arguments[0]).name not in self.command_allowlist:
            raise PermissionError(f"command is not allowlisted: {arguments[0] if arguments else ''}")
        executable = Path(arguments[0]).name
        if request.network_policy == "disabled" and executable not in {"python", "python3", "uv"}:
            raise PermissionError("the local network sandbox permits only Python or uv commands")
        if (
            request.network_policy == "disabled"
            and executable == "uv"
            and any(item in {"add", "pip", "sync", "tool"} for item in arguments[1:])
        ):
            raise PermissionError("dependency/network-changing uv commands are forbidden in the offline sandbox")
        guard_root = Path(__file__).with_name("network_guard")
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "ERL_RUN_ID": request.run_id,
            "ERL_EXPERIMENT_ID": request.experiment_id,
            "ERL_OUTPUT_DIR": str(output_root),
            "ERL_NETWORK_POLICY": request.network_policy,
            "PYTHONUNBUFFERED": "1",
            "PYTHONPATH": str(guard_root),
            "UV_OFFLINE": "1" if request.network_policy == "disabled" else "0",
            "CUDA_VISIBLE_DEVICES": "" if request.resources.gpu == 0 else os.environ.get("CUDA_VISIBLE_DEVICES", ""),
            "OMP_NUM_THREADS": str(request.resources.cpu),
            "OPENBLAS_NUM_THREADS": str(request.resources.cpu),
            "MKL_NUM_THREADS": str(request.resources.cpu),
        }
        environment_lock_hash, environment_lock_ref = _snapshot_environment_lock(self.workspace, output_root)
        usage_before = resource.getrusage(resource.RUSAGE_CHILDREN)
        started_at = datetime.now(UTC)
        started = time.monotonic()
        process = subprocess.Popen(
            arguments,
            cwd=self.workspace,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
            preexec_fn=lambda: _set_resource_limits(
                request.resources.cpu,
                request.resources.timeout_seconds,
                request.resources.memory_gb,
            ),
        )
        failure: FailureClass | None = None
        try:
            stdout, stderr = process.communicate(timeout=request.resources.timeout_seconds)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                stdout, stderr = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                stdout, stderr = process.communicate()
            failure = FailureClass.INFRASTRUCTURE
        wall = time.monotonic() - started
        completed_at = datetime.now(UTC)
        usage_after = resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu_seconds = (usage_after.ru_utime - usage_before.ru_utime) + (usage_after.ru_stime - usage_before.ru_stime)
        (output_root / "stdout.log").write_text(stdout, encoding="utf-8")
        (output_root / "stderr.log").write_text(stderr, encoding="utf-8")
        missing = [name for name in request.required_outputs if not (output_root / name).is_file()]
        if process.returncode != 0 and failure is None:
            failure = FailureClass.MODEL
        elif missing and failure is None:
            failure = FailureClass.IMPLEMENTATION
        metrics_path = output_root / "metrics.json"
        metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
        if not isinstance(metrics, dict):
            metrics = {}
            failure = FailureClass.IMPLEMENTATION
        # A failure class is a category; the next proposal needs the sentence. Without it the loop
        # can only learn "that design did not run", and re-proposes the same invalid argument.
        excerpt = None
        if failure is not None:
            tail = (stderr or stdout or "").strip().splitlines()[-12:]
            excerpt = "\n".join(tail)[-2000:] or None
            if missing:
                excerpt = f"missing required outputs: {missing}\n{excerpt or ''}".strip()[:2000]
        result = ExperimentResult(
            experiment_id=request.experiment_id,
            run_id=request.run_id,
            attempt=int(request.idempotency_key.rsplit("attempt-", 1)[1]),
            status="completed" if failure is None else "failed",
            exit_code=process.returncode,
            failure_class=failure,
            commit_sha=request.base_commit_sha,
            environment_hash=hashlib.sha256(
                (json.dumps(environment, sort_keys=True) + environment_lock_hash).encode()
            ).hexdigest(),
            environment_lock_hash=environment_lock_hash,
            dataset_fingerprint=request.dataset_fingerprint,
            metrics={str(key): float(value) for key, value in metrics.items() if isinstance(value, (int, float))},
            artifact_refs=[
                str(output_root / name) for name in request.required_outputs if (output_root / name).is_file()
            ]
            + [
                str(output_root / "stdout.log"),
                str(output_root / "stderr.log"),
                str(environment_lock_ref),
            ],
            runtime={"wall_seconds": wall},
            resource_usage=ObservedResourceUsage(
                cpu_hours=cpu_seconds / 3600,
                gpu_hours=(wall / 3600) * request.resources.gpu,
                wall_hours=wall / 3600,
                llm_tokens=None,
                peak_ram_gb=usage_after.ru_maxrss / (1024 * 1024),
            ),
            failure_excerpt=excerpt,
        )
        manifest_path = output_root / "erl_manifest.json"
        manifest = ExperimentManifest(
            experiment_id=request.experiment_id,
            run_id=request.run_id,
            system_mode=request.system_mode,
            request=request,
            result=result,
            environment_lock_hash=environment_lock_hash,
            environment_lock_ref=str(environment_lock_ref),
            fold_assignment_refs=[item for item in result.artifact_refs if "fold_assignment" in Path(item).name],
            submission_procedure=(
                request.command if any(Path(item).name == "submission.csv" for item in result.artifact_refs) else None
            ),
            started_at=started_at,
            completed_at=completed_at,
        )
        manifest_path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
        result = result.model_copy(
            update={
                "artifact_refs": [*result.artifact_refs, str(manifest_path)],
                "manifest_ref": str(manifest_path),
            }
        )
        self._result_path(request).write_text(result.model_dump_json(indent=2), encoding="utf-8")
        return result

    def result(self, request: ExperimentRequest) -> ExperimentResult | None:
        path = self._result_path(request)
        return ExperimentResult.model_validate_json(path.read_text(encoding="utf-8")) if path.exists() else None


def _snapshot_environment_lock(workspace: Path, output_root: Path) -> tuple[str, Path]:
    for name in ("uv.lock", "poetry.lock", "Pipfile.lock", "requirements.txt"):
        path = workspace / name
        if not path.is_file():
            continue
        snapshot = output_root / f"environment-lock-{name}"
        shutil.copy2(path, snapshot)
        digest = hashlib.sha256(name.encode() + path.read_bytes()).hexdigest()
        return digest, snapshot
    snapshot = output_root / "environment-lock-unavailable.txt"
    snapshot.write_text("No supported environment lockfile was present.\n", encoding="utf-8")
    return hashlib.sha256(b"environment-lock-unavailable").hexdigest(), snapshot


def _set_resource_limits(cpu_cores: int, timeout_seconds: int, memory_gb: float) -> None:
    cpu_seconds = max(1, int(timeout_seconds))
    memory_bytes = max(1, int(memory_gb * 1024**3))
    available = sorted(os.sched_getaffinity(0))
    os.sched_setaffinity(0, available[: min(cpu_cores, len(available))])
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
    resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
