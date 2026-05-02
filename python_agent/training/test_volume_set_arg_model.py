from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import joblib

from python_agent.nlu.normalizer import Normalizer


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "python_agent" / "data" / "volume_set" / "processed"
EVAL_DIR = PROJECT_ROOT / "python_agent" / "data" / "volume_set" / "eval"
MODEL_PATH = PROJECT_ROOT / "python_agent" / "models" / "volume_set_arg_model.joblib"
REPORT_PATH = EVAL_DIR / "test_results.json"


MANUAL_TESTS: list[dict[str, Any]] = [
    {"text": "звук на полную", "args": {"mode": "set", "percent": 100}},
    {"text": "громкость 80", "args": {"mode": "set", "percent": 80}},
    {"text": "поставь на половину", "args": {"mode": "set", "percent": 50}},
    {"text": "убавь на 20", "args": {"mode": "delta", "delta": -20}},
    {"text": "сделай громкость до 20", "args": {"mode": "set", "percent": 20}},
    {"text": "прибавь на 10", "args": {"mode": "delta", "delta": 10}},
    {"text": "погромче", "args": {"mode": "delta", "delta": 10}},
    {"text": "потише", "args": {"mode": "delta", "delta": -10}},
    {"text": "бивис сделай звук на семдесят пять", "args": {"mode": "set", "percent": 75}},
]


def normalize_prediction(prediction: dict[str, Any]) -> dict[str, Any]:
    mode = prediction.get("mode")
    if mode == "set":
        return {"mode": "set", "percent": int(prediction["percent"])}
    if mode == "delta":
        return {"mode": "delta", "delta": int(prediction["delta"])}
    if mode == "missing":
        return {"mode": "missing"}
    return {"mode": "invalid"}


def load_combined_examples(limit: int | None = None) -> list[dict[str, Any]]:
    path = DATA_DIR / "combined_examples.jsonl"
    if not path.exists():
        return []

    examples: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if not stripped:
                continue
            examples.append(json.loads(stripped))
            if limit is not None and len(examples) >= limit:
                break

    return examples


def run_cases(
    model: Any,
    normalizer: Normalizer,
    cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for case in cases:
        text = str(case["text"])
        expected = normalize_prediction(case["args"])
        normalized_text = normalizer.normalize(text)
        predicted_raw = model.predict([normalized_text])[0]
        predicted = normalize_prediction(predicted_raw)
        ok = predicted == expected

        results.append({
            "text": text,
            "normalized_text": normalized_text,
            "expected": expected,
            "predicted": predicted,
            "ok": ok,
            "confidence": predicted_raw.get("confidence"),
            "debug": predicted_raw.get("debug"),
        })

    return results


def summarize(name: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for item in results if item["ok"])
    return {
        "name": name,
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "accuracy": passed / total if total else 0.0,
    }


def main() -> int:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Missing model: {MODEL_PATH}")

    model = joblib.load(MODEL_PATH)
    normalizer = Normalizer()

    manual_results = run_cases(model, normalizer, MANUAL_TESTS)
    combined_results = run_cases(model, normalizer, load_combined_examples(limit=500))

    report = {
        "model_path": str(MODEL_PATH),
        "summary": [
            summarize("manual", manual_results),
            summarize("combined_first_500", combined_results),
        ],
        "manual_results": manual_results,
        "combined_failures": [item for item in combined_results if not item["ok"]][:50],
    }

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0 if all(item["failed"] == 0 for item in report["summary"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
