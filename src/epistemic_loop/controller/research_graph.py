from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from epistemic_loop.config import AppConfig, config_hash
from epistemic_loop.domain.enums import LoopState, Phase, RunStatus
from epistemic_loop.domain.events import EventType
from epistemic_loop.domain.models import CompetitionWorldModel, ResearchRun
from epistemic_loop.storage.repositories import ResearchRepository


class ResearchController:
    """Small application service; policies stay deterministic and event-sourced."""

    def __init__(self, repository: ResearchRepository):
        self.repository = repository

    def create_run(
        self,
        config: AppConfig,
        *,
        base_commit_sha: str,
        dataset_fingerprint: str,
        run_id: str | None = None,
    ) -> ResearchRun:
        identifier = run_id or config.run.id or f"{config.competition.slug}-{uuid.uuid4().hex[:8]}"
        run = ResearchRun(
            id=identifier,
            competition_id=config.competition.slug,
            mode=config.run.mode,
            phase=Phase.DISCOVERY,
            seed=config.run.seed,
            status=RunStatus.CREATED,
            base_commit_sha=base_commit_sha,
            dataset_fingerprint=dataset_fingerprint,
            config_hash=config_hash(config),
            budgets=config.budgets,
            holdout_policy=config.holdout,
        )
        self.repository.append(identifier, EventType.RUN_CREATED, run)
        self.repository.append(
            identifier,
            EventType.STATE_CHANGED,
            {"state": LoopState.CREATED.value, "run_status": RunStatus.CREATED.value},
        )
        return run

    def start(self, run_id: str, world_model: CompetitionWorldModel) -> None:
        self.repository.append(
            run_id,
            EventType.STATE_CHANGED,
            {"state": LoopState.OBSERVING.value, "run_status": RunStatus.RUNNING.value},
        )
        self.repository.append(run_id, EventType.WORLD_MODEL_RECORDED, world_model)
        self.repository.append(
            run_id,
            EventType.STATE_CHANGED,
            {"state": LoopState.HYPOTHESIZING.value, "run_status": RunStatus.RUNNING.value},
        )


def fingerprint_path(path: str | Path | None) -> str:
    if path is None:
        return hashlib.sha256(b"unavailable").hexdigest()
    target = Path(path)
    if not target.exists():
        return hashlib.sha256(f"missing:{target}".encode()).hexdigest()
    digest = hashlib.sha256()
    paths = sorted(target.rglob("*")) if target.is_dir() else [target]
    for item in paths:
        if not item.is_file():
            continue
        digest.update(str(item.relative_to(target) if target.is_dir() else item.name).encode())
        with item.open("rb") as file:
            for block in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()
