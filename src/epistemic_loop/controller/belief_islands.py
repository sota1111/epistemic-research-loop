from __future__ import annotations

import json
from pathlib import Path

from epistemic_loop.domain.models import AgentBeliefState, GlobalControlState


class BeliefAccessError(PermissionError):
    pass


class BeliefIslandStore:
    """Durable private state; only the owning agent can read or update an island."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def create(self, state: AgentBeliefState) -> None:
        path = self._path(state.agent_id)
        if path.exists():
            raise ValueError(f"belief island already exists: {state.agent_id}")
        self._write(path, state)

    def read(self, agent_id: str, *, requester: str) -> AgentBeliefState:
        self._authorize(agent_id, requester)
        path = self._path(agent_id)
        if not path.is_file():
            raise KeyError(f"unknown belief island: {agent_id}")
        return AgentBeliefState.model_validate_json(path.read_text(encoding="utf-8"))

    def update(self, state: AgentBeliefState, *, requester: str) -> None:
        self._authorize(state.agent_id, requester)
        if not self._path(state.agent_id).is_file():
            raise KeyError(f"unknown belief island: {state.agent_id}")
        self._write(self._path(state.agent_id), state)

    def agent_ids(self) -> tuple[str, ...]:
        return tuple(sorted(path.stem for path in self.root.glob("*.json")))

    @staticmethod
    def _authorize(agent_id: str, requester: str) -> None:
        if agent_id != requester:
            raise BeliefAccessError("agent belief, posterior and validation-world state are not cross-readable")

    def _path(self, agent_id: str) -> Path:
        if not agent_id or Path(agent_id).name != agent_id:
            raise ValueError("agent_id must be a safe path component")
        return self.root / f"{agent_id}.json"

    @staticmethod
    def _write(path: Path, state: AgentBeliefState) -> None:
        temporary = path.with_suffix(".tmp")
        temporary.write_text(state.model_dump_json(indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)


class GlobalControlPlane:
    """Shared scheduling state deliberately unable to store hypotheses or posteriors."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, state: GlobalControlState) -> None:
        payload = state.model_dump(mode="json")
        forbidden = {"hypotheses", "posterior", "global_best", "validation_world_beliefs"}
        if forbidden & set(payload):
            raise ValueError("global control plane cannot store agent belief or global-best state")
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    def load(self) -> GlobalControlState:
        if not self.path.is_file():
            raise FileNotFoundError(self.path)
        return GlobalControlState.model_validate_json(self.path.read_text(encoding="utf-8"))
