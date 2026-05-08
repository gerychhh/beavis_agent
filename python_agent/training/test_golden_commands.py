from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


from python_agent.core.pipeline import CommandPipeline


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_PATH = PROJECT_ROOT / "python_agent" / "data" / "eval" / "golden_commands.jsonl"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}: {error}") from error
            if not isinstance(row, dict):
                raise ValueError(f"Golden command row must be an object at {path}:{line_number}")
            rows.append(row)
    return rows


def compare_required_args(
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    for key, expected_value in expected.items():
        if key not in actual:
            errors.append(f"missing arg {key!r}")
            continue

        actual_value = actual[key]
        if actual_value != expected_value:
            errors.append(f"arg {key!r}: expected {expected_value!r}, got {actual_value!r}")
    return errors


def run_case(
    pipeline: CommandPipeline,
    case: dict[str, Any],
) -> dict[str, Any]:
    text = str(case.get("text", ""))
    expected_status = str(case.get("status", "ready"))
    expected_args = case.get("args", {})
    if not isinstance(expected_args, dict):
        return {
            "text": text,
            "ok": False,
            "errors": ["case args must be an object"],
        }

    decision = pipeline.build(text)
    errors: list[str] = []
    if decision.status != expected_status:
        errors.append(f"status: expected {expected_status!r}, got {decision.status!r}")

    if expected_status == "ready":
        expected_skill = str(case.get("skill", ""))
        if decision.tool_call is None:
            errors.append("missing tool_call for ready decision")
        else:
            if decision.tool_call.skill != expected_skill:
                errors.append(
                    f"skill: expected {expected_skill!r}, got {decision.tool_call.skill!r}"
                )
            errors.extend(compare_required_args(expected_args, decision.tool_call.args))
    elif expected_status in {"rejected", "needs_clarification", "error"}:
        expected_reason = case.get("reason")
        if expected_reason is not None and decision.reason != expected_reason:
            errors.append(f"reason: expected {expected_reason!r}, got {decision.reason!r}")

        expected_question_fragment = case.get("question_contains")
        if expected_question_fragment is not None:
            question = decision.question or ""
            if str(expected_question_fragment) not in question:
                errors.append(
                    f"question: expected to contain {expected_question_fragment!r}, got {question!r}"
                )
    else:
        errors.append(f"unsupported expected status: {expected_status!r}")

    return {
        "text": text,
        "ok": not errors,
        "errors": errors,
        "actual": {
            "status": decision.status,
            "reason": decision.reason,
            "question": decision.question,
            "skill": decision.tool_call.skill if decision.tool_call else None,
            "args": decision.tool_call.args if decision.tool_call else None,
        },
    }


def main() -> int:
    cases = read_jsonl(GOLDEN_PATH)
    pipeline = CommandPipeline()
    results = [run_case(pipeline, case) for case in cases]
    failures = [result for result in results if not result["ok"]]

    summary = {
        "total": len(results),
        "passed": len(results) - len(failures),
        "failed": len(failures),
        "golden_path": str(GOLDEN_PATH),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if failures:
        print("\nFailures:")
        for failure in failures:
            print(json.dumps(failure, ensure_ascii=False, indent=2))

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
