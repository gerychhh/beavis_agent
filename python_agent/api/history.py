from __future__ import annotations

from typing import Any

from python_agent.api.result import ok, fail
from python_agent.services.history_store import CommandHistoryStore


class HistoryApi:
    """
    Stable history API backed by CommandHistoryStore (python_agent/services/history_store.py).
    """

    def __init__(self, store: CommandHistoryStore | None = None) -> None:
        self.store = store or CommandHistoryStore()

    def list(self, limit: int = 120) -> dict[str, Any]:
        try:
            entries = self.store.load_entries(limit=limit)
            return ok([entry.to_display_dict() for entry in entries])
        except Exception as error:
            return fail(error, code="HISTORY_LIST_ERROR")

    def mark(self, request_id: str, status: str) -> dict[str, Any]:
        try:
            entries = self.store.load_entries(limit=10000)
            for entry in entries:
                if entry.request_id == request_id:
                    self.store.mark(entry, status=status)
                    return ok({"request_id": request_id, "status": status})

            return fail(f"request_id not found: {request_id}", code="HISTORY_ENTRY_NOT_FOUND")
        except Exception as error:
            return fail(error, code="HISTORY_MARK_ERROR")
