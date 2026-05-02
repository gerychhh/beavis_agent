from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXECUTABLE = (
    PROJECT_ROOT
    / "cpp_runtime"
    / "build"
    / "beavis_runtime.exe"
)
EXECUTABLE_CANDIDATES = (
    DEFAULT_EXECUTABLE,
    PROJECT_ROOT / "cpp_runtime" / "build" / "Debug" / "beavis_runtime.exe",
    PROJECT_ROOT / "cpp_runtime" / "build" / "Release" / "beavis_runtime.exe",
)


class CppClientError(RuntimeError):
    """Raised when the C++ runtime cannot be called or returns bad output."""


class CppClient:
    def __init__(
        self,
        executable_path: str | Path | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.executable_path = (
            Path(executable_path)
            if executable_path
            else self._find_default_executable()
        )
        self.timeout_seconds = timeout_seconds

    def execute(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        if not self.executable_path.exists():
            raise CppClientError(f"C++ runtime not found: {self.executable_path}")

        payload = json.dumps(tool_call, ensure_ascii=False)

        try:
            completed = subprocess.run(
                [str(self.executable_path)],
                input=payload,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
                encoding="utf-8",
            )
        except subprocess.TimeoutExpired as error:
            raise CppClientError("C++ runtime timed out") from error
        except OSError as error:
            raise CppClientError(f"Failed to start C++ runtime: {error}") from error

        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()

        if completed.returncode != 0:
            details = stderr or stdout or f"exit code {completed.returncode}"
            raise CppClientError(f"C++ runtime failed: {details}")

        if not stdout:
            raise CppClientError("C++ runtime returned empty stdout")

        try:
            result = json.loads(stdout)
        except json.JSONDecodeError as error:
            raise CppClientError(f"C++ runtime returned invalid JSON: {stdout}") from error

        if not isinstance(result, dict):
            raise CppClientError("C++ runtime result must be a JSON object")

        return result

    def _find_default_executable(self) -> Path:
        for candidate in EXECUTABLE_CANDIDATES:
            if candidate.exists():
                return candidate

        return DEFAULT_EXECUTABLE


def execute_tool_call(
    tool_call: dict[str, Any],
    executable_path: str | Path | None = None,
) -> dict[str, Any]:
    return CppClient(executable_path=executable_path).execute(tool_call)


if __name__ == "__main__":
    sample_tool_call = {
        "request_id": "cmd_001",
        "type": "tool_call",
        "skill": "volume_set",
        "args": {
            "percent": 100,
        },
        "meta": {
            "source": "text",
            "raw_text": "звук на полную",
            "normalized_text": "звук на полную",
            "skill_confidence": 0.94,
            "args_confidence": 0.95,
        },
    }

    result = execute_tool_call(sample_tool_call)
    print(json.dumps(result, ensure_ascii=False, indent=2))
