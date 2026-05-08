from __future__ import annotations

from python_agent.core.schemas import SkillResult, ToolCall
from python_agent.cpp_client import CppClient, CppClientError


class CommandExecutor:
    def __init__(self, cpp_client: CppClient | None = None) -> None:
        self.cpp_client = cpp_client or CppClient()

    def execute(self, tool_call: ToolCall) -> SkillResult:
        try:
            payload = self.cpp_client.execute(tool_call.to_dict())
            return SkillResult.from_dict(payload)
        except CppClientError as error:
            return SkillResult(
                request_id=tool_call.request_id,
                success=False,
                skill=tool_call.skill,
                message=str(error),
                error={
                    "code": "CPP_RUNTIME_ERROR",
                    "details": str(error),
                },
            )
