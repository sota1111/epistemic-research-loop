from __future__ import annotations

import hashlib
import json
import os
import shlex
import signal
import subprocess
import time
from pathlib import Path

from epistemic_loop.adapters.executor.base import ExecutorAdapter
from epistemic_loop.domain.enums import FailureClass
from epistemic_loop.domain.models import ExperimentRequest, ExperimentResult


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
        arguments = shlex.split(request.command)
        if not arguments or Path(arguments[0]).name not in self.command_allowlist:
            raise PermissionError(f"command is not allowlisted: {arguments[0] if arguments else ''}")
        output_root = self._result_path(request).parent
        output_root.mkdir(parents=True, exist_ok=True)
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "ERL_RUN_ID": request.run_id,
            "ERL_EXPERIMENT_ID": request.experiment_id,
            "ERL_OUTPUT_DIR": str(output_root),
            "ERL_NETWORK_POLICY": request.network_policy,
            "PYTHONUNBUFFERED": "1",
        }
        started = time.monotonic()
        process = subprocess.Popen(
            arguments,
            cwd=self.workspace,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
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
        result = ExperimentResult(
            experiment_id=request.experiment_id,
            run_id=request.run_id,
            attempt=1,
            status="completed" if failure is None else "failed",
            exit_code=process.returncode,
            failure_class=failure,
            commit_sha=request.base_commit_sha,
            environment_hash=hashlib.sha256(json.dumps(environment, sort_keys=True).encode()).hexdigest(),
            dataset_fingerprint="local-executor-unverified",
            metrics={str(key): float(value) for key, value in metrics.items() if isinstance(value, (int, float))},
            artifact_refs=[
                str(output_root / name) for name in request.required_outputs if (output_root / name).is_file()
            ],
            runtime={"wall_seconds": wall},
        )
        self._result_path(request).write_text(result.model_dump_json(indent=2), encoding="utf-8")
        return result

    def result(self, request: ExperimentRequest) -> ExperimentResult | None:
        path = self._result_path(request)
        return ExperimentResult.model_validate_json(path.read_text(encoding="utf-8")) if path.exists() else None
