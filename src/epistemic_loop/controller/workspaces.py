from __future__ import annotations

import re
import subprocess
from pathlib import Path

_SAFE_AGENT = re.compile(r"^agent-[a-z0-9][a-z0-9-]*$")


class AgentWorkspaceManager:
    """Create generic branch/worktree islands and enforce owner-only lookup."""

    def __init__(self, repository: str | Path, workspace_root: str | Path):
        self.repository = Path(repository).resolve()
        self.workspace_root = Path(workspace_root).resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)

    def create(self, agent_id: str, *, base_ref: str) -> Path:
        self._validate_agent(agent_id)
        path = self.workspace_root / agent_id
        if path.exists():
            raise FileExistsError(path)
        branch = f"agents/{agent_id}"
        subprocess.run(
            ["git", "-C", str(self.repository), "worktree", "add", "-b", branch, str(path), base_ref],
            check=True,
            capture_output=True,
            text=True,
        )
        return path

    def resolve(self, agent_id: str, *, requester: str) -> Path:
        self._validate_agent(agent_id)
        if requester != agent_id:
            raise PermissionError("agents cannot inspect or modify another agent worktree")
        path = self.workspace_root / agent_id
        if not path.is_dir():
            raise KeyError(f"unknown agent workspace: {agent_id}")
        return path

    @staticmethod
    def _validate_agent(agent_id: str) -> None:
        if not _SAFE_AGENT.fullmatch(agent_id):
            raise ValueError("agent_id must use the generic agent-<name> form")
