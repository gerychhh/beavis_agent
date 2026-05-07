from __future__ import annotations

import argparse
import json
import sys

from python_agent.bridge.router import BridgeRouter


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    parser = argparse.ArgumentParser(description="One-shot Beavis API bridge")
    parser.add_argument("method", help="API method, e.g. commands.run")
    parser.add_argument("params", nargs="?", default="{}", help="JSON params object")
    args = parser.parse_args()

    try:
        params = json.loads(args.params)
        if not isinstance(params, dict):
            raise ValueError("params must be a JSON object")

        result = BridgeRouter().dispatch(args.method, params)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1

    except Exception as error:
        print(json.dumps({
            "ok": False,
            "data": None,
            "error": str(error),
            "code": "ONESHOT_ERROR",
            "meta": {},
        }, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
