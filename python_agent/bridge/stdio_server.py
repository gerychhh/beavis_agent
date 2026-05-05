from __future__ import annotations

import json
import sys
from typing import Any

from python_agent.bridge.router import BridgeRouter


def _json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def main() -> int:
    """
    Persistent JSON-lines bridge.

    Request line:
      {"id":"1","method":"commands.run","params":{"text":"звук на 50","execute":false}}

    Response line:
      {"id":"1","ok":true,"data":...,"error":null,"code":null,"meta":{}}
    """

    router = BridgeRouter()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        request_id: str | int | None = None

        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("Request must be a JSON object")

            request_id = request.get("id")
            method = str(request.get("method") or "")
            params = request.get("params") or {}

            if not isinstance(params, dict):
                raise ValueError("params must be a JSON object")

            result = router.dispatch(method, params)
            response = {"id": request_id, **result}

        except Exception as error:
            response = {
                "id": request_id,
                "ok": False,
                "data": None,
                "error": str(error),
                "code": "BRIDGE_REQUEST_ERROR",
                "meta": {},
            }

        print(_json_dumps(response), flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
