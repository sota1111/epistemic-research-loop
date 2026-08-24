from typing import Any, Protocol


class Tracker(Protocol):
    def record(self, event: dict[str, Any]) -> None: ...
