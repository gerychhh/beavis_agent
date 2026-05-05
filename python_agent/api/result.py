from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ApiResult:
    ok: bool
    data: Any = None
    error: str | None = None
    code: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "data": self.data,
            "error": self.error,
            "code": self.code,
            "meta": self.meta,
        }


def ok(data: Any = None, **meta: Any) -> dict[str, Any]:
    return ApiResult(ok=True, data=data, error=None, code=None, meta=meta).to_dict()


def fail(error: Exception | str, code: str = "ERROR", **meta: Any) -> dict[str, Any]:
    return ApiResult(
        ok=False,
        data=None,
        error=str(error),
        code=code,
        meta=meta,
    ).to_dict()
