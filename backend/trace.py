"""Agent trace primitives.

Every stage of the pipeline records an AgentAction so the user can see the
agent's step-by-step reasoning, not just the final output.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentAction:
    """One inspectable step of the agent loop."""

    id: str
    name: str
    status: str = "running"  # running | done | failed
    input: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)
    duration_ms: float = 0.0
    error: str | None = None

    def finish(self, output: dict[str, Any]) -> None:
        self.output = output
        self.status = "done"
        self.duration_ms = round((time.time() - self.started_at) * 1000, 1)

    def fail(self, error: str) -> None:
        self.error = error
        self.status = "failed"
        self.duration_ms = round((time.time() - self.started_at) * 1000, 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "input": self.input,
            "output": self.output,
            "started_at": self.started_at,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


class Trace:
    """Ordered list of agent actions, returned in every /api/run response."""

    def __init__(self) -> None:
        self.actions: list[AgentAction] = []
        self._counter = 0

    def start(self, name: str, **input_: Any) -> AgentAction:
        self._counter += 1
        action = AgentAction(
            id=f"step-{self._counter}",
            name=name,
            input=input_,
        )
        self.actions.append(action)
        return action

    def to_list(self) -> list[dict[str, Any]]:
        return [a.to_dict() for a in self.actions]
