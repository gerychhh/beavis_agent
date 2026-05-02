from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from python_agent.nlu.normalizer import Normalizer


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []

    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    return rows


def is_match(predicted: dict, expected: dict) -> bool:
    if "missing" in expected:
        if predicted.get("missing") != expected.get("missing"):
            return False

        if "action" in expected and predicted.get("action") != expected.get("action"):
            return False

        return True

    if predicted.get("action") != expected.get("action"):
        return False

    if predicted.get("target_type") != expected.get("target_type"):
        return False

    if expected.get("target_type") == "app":
        return predicted.get("app_id") == expected.get("app_id")

    return True


def main() -> None:
    model_path = ROOT / "python_agent" / "models" / "window_control_arg_model.joblib"
    eval_dir = ROOT / "python_agent" / "data" / "window_control" / "eval"

    model = joblib.load(model_path)
    normalizer = Normalizer()

    manual_tests = read_jsonl(eval_dir / "manual_tests.jsonl")
    texts = [normalizer.normalize(row["text"]) for row in manual_tests]
    predictions = model.predict(texts)

    result_rows: list[dict] = []
    correct = 0

    for row, prediction in zip(manual_tests, predictions):
        ok = is_match(prediction, row["expected"])
        correct += int(ok)
        result_rows.append({
            "text": row["text"],
            "expected": row["expected"],
            "predicted": prediction,
            "ok": ok,
        })

    result = {
        "total": len(result_rows),
        "correct": correct,
        "accuracy": correct / len(result_rows) if result_rows else 0.0,
        "rows": result_rows,
    }

    (eval_dir / "test_results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps({
        "total": result["total"],
        "correct": result["correct"],
        "accuracy": result["accuracy"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
