from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


from python_agent.nlu.argument_extractors.web_search import WebSearchExtractor


CASES: list[dict[str, Any]] = [
    {
        "text": "найди rust ownership",
        "args": {
            "action": "search",
            "provider": "google",
            "query": "rust ownership",
            "url": "https://www.google.com/search?q=rust+ownership",
        },
    },
    {
        "text": "загугли рецепт сырников",
        "args": {
            "action": "search",
            "provider": "google",
            "query": "рецепт сырников",
            "url": "https://www.google.com/search?q=%D1%80%D0%B5%D1%86%D0%B5%D0%BF%D1%82+%D1%81%D1%8B%D1%80%D0%BD%D0%B8%D0%BA%D0%BE%D0%B2",
        },
    },
    {
        "text": "google tauri build windows",
        "args": {
            "action": "search",
            "provider": "google",
            "query": "tauri build windows",
            "url": "https://www.google.com/search?q=tauri+build+windows",
        },
    },
    {
        "text": "найди",
        "args": {},
        "missing": ["query"],
    },
]


def main() -> int:
    extractor = WebSearchExtractor()
    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for case in CASES:
        prediction = extractor.extract(str(case["text"]))
        expected = case["args"]
        expected_missing = case.get("missing", [])
        actual = prediction.args
        errors = [
            f"{key}: expected {value!r}, got {actual.get(key)!r}"
            for key, value in expected.items()
            if actual.get(key) != value
        ]
        if prediction.missing != expected_missing:
            errors.append(f"missing: expected {expected_missing!r}, got {prediction.missing!r}")
        result = {
            "text": case["text"],
            "ok": not errors,
            "errors": errors,
            "actual": actual,
            "missing": prediction.missing,
        }
        results.append(result)
        if not result["ok"]:
            failures.append(result)

    print(json.dumps({
        "total": len(results),
        "passed": len(results) - len(failures),
        "failed": len(failures),
    }, ensure_ascii=False, indent=2))

    if failures:
        print(json.dumps(failures, ensure_ascii=False, indent=2))

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
