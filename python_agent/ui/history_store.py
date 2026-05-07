from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from python_agent.core.logger import DEFAULT_LOG_PATH


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FEEDBACK_PATH = PROJECT_ROOT / "python_agent" / "data" / "feedback" / "command_feedback.jsonl"


@dataclass(frozen=True)
class HistoryEntry:
    record: dict[str, Any]
    feedback: dict[str, Any] | None = None

    @property
    def request_id(self) -> str:
        return str(self.record.get("request_id") or "")

    @property
    def timestamp(self) -> str:
        return str(self.record.get("timestamp") or "")

    @property
    def raw_text(self) -> str:
        return readable_text(str(self.record.get("raw_text") or ""))

    @property
    def normalized_text(self) -> str:
        return readable_text(str(self.record.get("normalized_text") or ""))

    @property
    def skill(self) -> str:
        nlu = self.record.get("nlu")
        if isinstance(nlu, dict):
            return str(nlu.get("predicted_skill") or "")
        return ""

    @property
    def source(self) -> str:
        tool_call = self.record.get("tool_call")
        if isinstance(tool_call, dict):
            meta = tool_call.get("meta")
            if isinstance(meta, dict):
                return str(meta.get("source") or "text")
        return "text"

    @property
    def args(self) -> dict[str, Any]:
        nlu = self.record.get("nlu")
        if isinstance(nlu, dict) and isinstance(nlu.get("predicted_args"), dict):
            return nlu["predicted_args"]
        return {}

    @property
    def confidence(self) -> str:
        nlu = self.record.get("nlu")
        if not isinstance(nlu, dict):
            return ""

        skill_conf = _float_or_none(nlu.get("skill_confidence"))
        args_conf = _float_or_none(nlu.get("args_confidence"))
        if skill_conf is None and args_conf is None:
            return ""
        if skill_conf is None:
            return f"args {args_conf:.2f}"
        if args_conf is None:
            return f"skill {skill_conf:.2f}"
        return f"{skill_conf:.2f} / {args_conf:.2f}"

    @property
    def result(self) -> str:
        result = self.record.get("execution_result")
        if not isinstance(result, dict):
            return "ToolCall"
        if result.get("success"):
            return readable_text(str(result.get("message") or "OK"))
        return readable_text(str(result.get("message") or "Ошибка"))

    @property
    def feedback_status(self) -> str:
        if not self.feedback:
            return "candidate"
        return str(self.feedback.get("status") or "candidate")

    def feedback_label(self) -> str:
        status = self.feedback_status
        if status == "correct":
            return "верно"
        if status == "incorrect":
            return "ошибка"
        return "не отмечено"

    def to_display_dict(self) -> dict[str, Any]:
        payload = dict(self.record)
        status = self.feedback_status
        if status == "candidate":
            status = "pending"

        skill_confidence = 0.0
        nlu = self.record.get("nlu")
        if isinstance(nlu, dict):
            parsed = _float_or_none(nlu.get("skill_confidence"))
            if parsed is not None:
                skill_confidence = parsed

        payload["id"] = self.request_id
        payload["date"] = self.timestamp
        payload["raw_text"] = self.raw_text
        payload["normalized_text"] = self.normalized_text
        payload["skill"] = self.skill
        payload["confidence"] = skill_confidence
        payload["result"] = self.result
        payload["status"] = status
        payload["source"] = self.source
        payload["args"] = self.args
        payload["raw_text_display"] = self.raw_text
        payload["normalized_text_display"] = self.normalized_text
        payload["feedback"] = self.feedback
        return payload


class CommandHistoryStore:
    def __init__(
        self,
        log_path: str | Path | None = None,
        feedback_path: str | Path | None = None,
    ) -> None:
        self.log_path = Path(log_path) if log_path else DEFAULT_LOG_PATH
        self.feedback_path = Path(feedback_path) if feedback_path else DEFAULT_FEEDBACK_PATH

    def load_entries(self, limit: int = 120) -> list[HistoryEntry]:
        feedback = self._load_feedback_by_request_id()
        records = _read_jsonl(self.log_path, limit=limit)
        entries = [
            HistoryEntry(record=record, feedback=feedback.get(str(record.get("request_id") or "")))
            for record in records
            if isinstance(record.get("request_id"), str)
        ]
        entries.reverse()
        return entries[:limit]

    def mark(self, entry: HistoryEntry, status: str) -> None:
        if status not in {"correct", "incorrect"}:
            raise ValueError(f"Unsupported feedback status: {status}")

        record = entry.record
        nlu = record.get("nlu") if isinstance(record.get("nlu"), dict) else {}
        result = record.get("execution_result") if isinstance(record.get("execution_result"), dict) else None

        feedback_record = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "request_id": entry.request_id,
            "status": status,
            "raw_text": record.get("raw_text"),
            "raw_text_display": entry.raw_text,
            "normalized_text": record.get("normalized_text"),
            "normalized_text_display": entry.normalized_text,
            "predicted_skill": nlu.get("predicted_skill"),
            "predicted_args": nlu.get("predicted_args"),
            "skill_confidence": nlu.get("skill_confidence"),
            "args_confidence": nlu.get("args_confidence"),
            "execution_success": result.get("success") if isinstance(result, dict) else None,
            "source": "ui_history",
        }

        self.feedback_path.parent.mkdir(parents=True, exist_ok=True)
        with self.feedback_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(feedback_record, ensure_ascii=False) + "\n")

    def _load_feedback_by_request_id(self) -> dict[str, dict[str, Any]]:
        feedback_by_id: dict[str, dict[str, Any]] = {}
        for record in _read_jsonl(self.feedback_path):
            request_id = str(record.get("request_id") or "")
            if request_id:
                feedback_by_id[request_id] = record
        return feedback_by_id


def _read_jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    try:
        if limit is not None and limit > 0:
            lines = _read_recent_lines(path, int(limit))
        else:
            lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    records: list[dict[str, Any]] | deque[dict[str, Any]]
    records = deque(maxlen=max(1, int(limit))) if limit is not None and limit > 0 else []
    for line in lines:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)

    return list(records)


def _read_recent_lines(path: Path, limit: int, block_size: int = 8192) -> list[str]:
    if limit <= 0:
        return []

    chunks: list[bytes] = []
    line_breaks = 0
    with path.open("rb") as file:
        file.seek(0, 2)
        position = file.tell()

        while position > 0 and line_breaks <= limit:
            read_size = min(block_size, position)
            position -= read_size
            file.seek(position)
            chunk = file.read(read_size)
            chunks.append(chunk)
            line_breaks += chunk.count(b"\n")

    if not chunks:
        return []

    text = b"".join(reversed(chunks)).decode("utf-8", errors="replace")
    return text.splitlines()[-limit:]


def readable_text(value: str) -> str:
    if not value:
        return ""

    try:
        repaired = value.encode("cp1251").decode("utf-8")
    except UnicodeError:
        return value

    if _mojibake_score(value) >= 2 and _mojibake_score(repaired) < _mojibake_score(value):
        return repaired

    return value


def _mojibake_score(value: str) -> int:
    return value.count("Р") + value.count("С") + value.count("Ð") + value.count("Ñ")


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
