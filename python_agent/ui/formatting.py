from __future__ import annotations

import json

from python_agent.core.schemas import PipelineOutput


def output_to_json(output: PipelineOutput) -> str:
    return json.dumps(output.to_dict(), ensure_ascii=False, indent=2)


def error_to_json(message: str) -> str:
    return json.dumps({"success": False, "error": message}, ensure_ascii=False, indent=2)


def output_title(output: PipelineOutput) -> str:
    result = output.execution_result
    if result is None:
        return f"ToolCall готов: {output.tool_call.skill}"

    if result.success:
        return result.message or f"Готово: {result.skill}"

    return result.message or "Команда не выполнена"


def output_summary(output: PipelineOutput) -> str:
    skill = output.skill_prediction.skill
    skill_conf = output.skill_prediction.confidence
    args_conf = output.args_prediction.confidence
    args = json.dumps(output.args_prediction.args, ensure_ascii=False)

    lines = [
        f"skill: {skill} ({skill_conf:.3f})",
        f"args: {args} ({args_conf:.3f})",
    ]

    result = output.execution_result
    if result is not None:
        state = "success" if result.success else "failed"
        lines.append(f"result: {state}")
        if result.message:
            lines.append(f"message: {result.message}")

    return "\n".join(lines)
