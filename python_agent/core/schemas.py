from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SkillPrediction:
    skill: str
    confidence: float
    source: str = "rules_mvp"

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill": self.skill,
            "confidence": self.confidence,
            "source": self.source,
        }


@dataclass(frozen=True)
class ArgsPrediction:
    args: dict[str, Any]
    confidence: float
    missing: list[str] = field(default_factory=list)
    source: str = "rules_mvp"

    def to_dict(self) -> dict[str, Any]:
        return {
            "args": self.args,
            "confidence": self.confidence,
            "missing": self.missing,
            "source": self.source,
        }


@dataclass(frozen=True)
class ToolCall:
    request_id: str
    skill: str
    args: dict[str, Any]
    meta: dict[str, Any] = field(default_factory=dict)
    type: str = "tool_call"

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "request_id": self.request_id,
            "type": self.type,
            "skill": self.skill,
            "args": self.args,
        }

        if self.meta:
            payload["meta"] = self.meta

        return payload


@dataclass(frozen=True)
class SkillResult:
    request_id: str | None
    success: bool
    skill: str | None
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    error: dict[str, Any] | None = None
    type: str = "skill_result"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SkillResult":
        data = payload.get("data") or {}
        error = payload.get("error")

        return cls(
            request_id=payload.get("request_id"),
            type=payload.get("type", "skill_result"),
            success=bool(payload.get("success", False)),
            skill=payload.get("skill"),
            message=str(payload.get("message", "")),
            data=data if isinstance(data, dict) else {},
            error=error if isinstance(error, dict) or error is None else {"details": str(error)},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "type": self.type,
            "success": self.success,
            "skill": self.skill,
            "message": self.message,
            "data": self.data,
            "error": self.error,
        }


@dataclass(frozen=True)
class PipelineOutput:
    raw_text: str
    normalized_text: str
    skill_prediction: SkillPrediction
    args_prediction: ArgsPrediction
    tool_call: ToolCall
    execution_result: SkillResult | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "skill_prediction": self.skill_prediction.to_dict(),
            "args_prediction": self.args_prediction.to_dict(),
            "tool_call": self.tool_call.to_dict(),
            "execution_result": (
                self.execution_result.to_dict()
                if self.execution_result is not None
                else None
            ),
        }
