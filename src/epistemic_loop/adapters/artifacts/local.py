from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from epistemic_loop.adapters.artifacts.base import ArtifactStore
from epistemic_loop.domain.models import ArtifactRef


class LocalArtifactStore(ArtifactStore):
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

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
        source = source.resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        destination = self.root / run_id / experiment_id / f"{digest}-{source.name}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copyfile(source, destination)
        if sealed:
            destination.chmod(0o600)
        return ArtifactRef(
            uri=f"artifact://runs/{run_id}/{experiment_id}/{destination.name}",
            sha256=digest,
            experiment_id=experiment_id,
            code_commit_sha=code_commit_sha,
            dataset_fingerprint=dataset_fingerprint,
            environment_hash=environment_hash,
            mime_type=mime_type,
            size=destination.stat().st_size,
            sealed=sealed,
        )
