from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from python_agent.core.schemas import ToolCall


CommandDecisionStatus = Literal["ready", "rejected", "needs_clarification", "error"]


@dataclass(frozen=True)
class CommandDecision:
    status: CommandDecisionStatus
    raw_text: str
    normalized_text: str
    tool_call: ToolCall | None = None
    reason: str | None = None
    question: str | None = None
    debug: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "tool_call": self.tool_call.to_dict() if self.tool_call else None,
            "reason": self.reason,
            "question": self.question,
            "debug": self.debug,
        }
