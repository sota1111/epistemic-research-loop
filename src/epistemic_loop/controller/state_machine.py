from __future__ import annotations

from dataclasses import dataclass

from epistemic_loop.domain.enums import LoopState

TRANSITIONS: dict[LoopState, frozenset[LoopState]] = {
    LoopState.CREATED: frozenset({LoopState.OBSERVING, LoopState.BLOCKED, LoopState.FAILED}),
    LoopState.OBSERVING: frozenset({LoopState.HYPOTHESIZING, LoopState.BLOCKED, LoopState.FAILED}),
    LoopState.HYPOTHESIZING: frozenset({LoopState.PLANNING, LoopState.BLOCKED, LoopState.FAILED}),
    LoopState.PLANNING: frozenset({LoopState.SCORING, LoopState.FINALIZING, LoopState.BLOCKED, LoopState.FAILED}),
    LoopState.SCORING: frozenset({LoopState.SELECTING, LoopState.BLOCKED, LoopState.FAILED}),
    LoopState.SELECTING: frozenset({LoopState.EXECUTING, LoopState.PLANNING, LoopState.FINALIZING, LoopState.BLOCKED}),
    LoopState.EXECUTING: frozenset({LoopState.PARSING, LoopState.PLANNING, LoopState.BLOCKED, LoopState.FAILED}),
    LoopState.PARSING: frozenset({LoopState.FALSIFYING, LoopState.PLANNING, LoopState.FAILED}),
    LoopState.FALSIFYING: frozenset({LoopState.UPDATING, LoopState.FAILED}),
    LoopState.UPDATING: frozenset({LoopState.PHASE_DECISION, LoopState.FAILED}),
    LoopState.PHASE_DECISION: frozenset(
        {
            LoopState.HYPOTHESIZING,
            LoopState.PLANNING,
            LoopState.EXPLOITER_HANDOFF,
            LoopState.FINALIZING,
            LoopState.BLOCKED,
        }
    ),
    LoopState.EXPLOITER_HANDOFF: frozenset({LoopState.PLANNING, LoopState.FINALIZING, LoopState.BLOCKED}),
    LoopState.FINALIZING: frozenset({LoopState.COMPLETED, LoopState.BLOCKED, LoopState.FAILED}),
    LoopState.COMPLETED: frozenset(),
    LoopState.BLOCKED: frozenset(),
    LoopState.FAILED: frozenset(),
}


class InvalidTransition(ValueError):
    pass


@dataclass
class ResearchStateMachine:
    state: LoopState = LoopState.CREATED

    def transition(self, target: LoopState) -> LoopState:
        if target not in TRANSITIONS[self.state]:
            raise InvalidTransition(f"invalid transition: {self.state.value} -> {target.value}")
        self.state = target
        return target
