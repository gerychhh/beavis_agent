from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


from python_agent.nlu.argument_extractors.web_open import WebOpenExtractor


CASES: list[dict[str, Any]] = [
    {
        "text": "открой github",
        "args": {
            "action": "open",
            "site_id": "github",
            "url": "https://github.com",
        },
    },
    {
        "text": "перейди на ютуб",
        "args": {
            "action": "open",
            "site_id": "youtube",
            "url": "https://www.youtube.com",
        },
    },
    {
        "text": "открой google",
        "args": {
            "action": "open",
            "site_id": "google",
            "url": "https://www.google.com",
        },
    },
    {
        "text": "открой github.com/openai/codex",
        "args": {
            "action": "open",
            "url": "https://github.com/openai/codex",
        },
    },
    {
        "text": "open https://example.com/docs?a=1",
        "args": {
            "action": "open",
            "url": "https://example.com/docs?a=1",
        },
    },
    {
        "text": "найди rust ownership",
        "args": {},
        "missing": ["url"],
    },
    {
        "text": "поищи lofi mix на ютубе",
        "args": {},
        "missing": ["url"],
    },
]


def main() -> int:
    extractor = WebOpenExtractor()
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
