from __future__ import annotations

import argparse
import json
from pathlib import Path

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import joblib

from python_agent.nlu.normalizer import Normalizer


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def predicted_app_id(pred: dict) -> str:
    return pred.get("app_id", "unknown")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=Path, default=Path("python_agent/models/open_app_arg_model.joblib"))
    parser.add_argument("--tests-path", type=Path, default=Path("python_agent/data/open_app/eval/manual_tests.jsonl"))
    parser.add_argument("--results-path", type=Path, default=Path("python_agent/data/open_app/eval/test_results.json"))
    args = parser.parse_args()

    model = joblib.load(args.model_path)
    tests = read_jsonl(args.tests_path)
    normalizer = Normalizer()

    results = []
    correct = 0

    for item in tests:
        text = item["text"]
        normalized_text = normalizer.normalize(text)
        expected = item["expected_app_id"]

        pred = model.predict([normalized_text])[0]
        got = predicted_app_id(pred)
        ok = got == expected

        if ok:
            correct += 1

        results.append({
            "text": text,
            "normalized_text": normalized_text,
            "expected_app_id": expected,
            "prediction": pred,
            "predicted_app_id": got,
            "ok": ok,
        })

    summary = {
        "total": len(tests),
        "correct": correct,
        "accuracy": correct / len(tests) if tests else 0.0,
        "errors": [row for row in results if not row["ok"]],
        "results": results,
    }

    args.results_path.parent.mkdir(parents=True, exist_ok=True)
    args.results_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "total": summary["total"],
        "correct": summary["correct"],
        "accuracy": round(summary["accuracy"], 4),
        "errors_count": len(summary["errors"]),
        "results_path": str(args.results_path),
    }, ensure_ascii=False, indent=2))

    if summary["errors"]:
        print("\nErrors:")
        for err in summary["errors"][:30]:
            print(f"- {err['text']!r}: expected={err['expected_app_id']}, got={err['predicted_app_id']}, pred={err['prediction']}")


if __name__ == "__main__":
    main()
