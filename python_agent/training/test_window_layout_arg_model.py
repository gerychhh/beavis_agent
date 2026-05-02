from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


MODEL_PATH = ROOT / "python_agent" / "models" / "window_layout_arg_model.joblib"
MANUAL_TESTS_PATH = ROOT / "python_agent" / "data" / "window_layout" / "eval" / "manual_tests.jsonl"
RESULTS_PATH = ROOT / "python_agent" / "data" / "window_layout" / "eval" / "test_results.json"


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def is_correct(expected: dict, actual: dict) -> bool:
    if "missing" in expected:
        return "missing" in actual

    if actual.get("layout") != expected.get("layout"):
        return False

    return actual.get("targets", []) == expected.get("targets", [])


def main():
    model = joblib.load(MODEL_PATH)
    tests = load_jsonl(MANUAL_TESTS_PATH)

    texts = [row["text"] for row in tests]
    predictions = model.predict(texts)

    rows = []
    correct = 0
    for test, pred in zip(tests, predictions):
        ok = is_correct(test["expected"], pred)
        correct += int(ok)
        rows.append({
            "text": test["text"],
            "expected": test["expected"],
            "predicted": pred,
            "correct": ok,
        })

    summary = {
        "total": len(tests),
        "correct": correct,
        "accuracy": correct / len(tests) if tests else 0.0,
        "rows": rows,
    }

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "total": summary["total"],
        "correct": summary["correct"],
        "accuracy": summary["accuracy"],
        "results_path": str(RESULTS_PATH),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
