from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from epistemic_loop.domain.models import ArtifactRef


class ArtifactStore(ABC):
    @abstractmethod
    def put(
        self,
        source: Path,
        *,
        run_id: str,
        experiment_id: str,
        code_commit_sha: str,
        dataset_fingerprint: str,
        environment_hash: str,
        mime_type: str,
        sealed: bool = False,
    ) -> ArtifactRef:
        raise NotImplementedError
