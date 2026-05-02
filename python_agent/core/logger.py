from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from python_agent.core.schemas import PipelineOutput


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_PATH = PROJECT_ROOT / "python_agent" / "data" / "logs" / "actions.jsonl"


class ActionLogger:
    def __init__(self, log_path: str | Path | None = None) -> None:
        self.log_path = Path(log_path) if log_path else DEFAULT_LOG_PATH

    def log(self, output: PipelineOutput, training_status: str = "candidate") -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        record: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "request_id": output.tool_call.request_id,
            "raw_text": output.raw_text,
            "normalized_text": output.normalized_text,
            "nlu": {
                "predicted_skill": output.skill_prediction.skill,
                "skill_confidence": output.skill_prediction.confidence,
                "predicted_args": output.args_prediction.args,
                "args_confidence": output.args_prediction.confidence,
                "missing": output.args_prediction.missing,
                "source": output.args_prediction.source,
            },
            "tool_call": output.tool_call.to_dict(),
            "execution_result": (
                output.execution_result.to_dict()
                if output.execution_result is not None
                else None
            ),
            "training_status": training_status,
        }

        with self.log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
