from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from python_agent.nlu.normalizer import Normalizer
from python_agent.nlu.skill_classifier import ModelSkillClassifier


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "python_agent" / "models" / "skill_classifier.joblib"
DEFAULT_TESTS_PATH = PROJECT_ROOT / "python_agent" / "data" / "skill_classifier" / "eval" / "manual_tests.jsonl"
DEFAULT_RESULTS_PATH = PROJECT_ROOT / "python_agent" / "data" / "skill_classifier" / "eval" / "test_results.json"


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Test top-level skill classifier")
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--tests-path", type=Path, default=DEFAULT_TESTS_PATH)
    parser.add_argument("--results-path", type=Path, default=DEFAULT_RESULTS_PATH)
    args = parser.parse_args()

    normalizer = Normalizer()
    classifier = ModelSkillClassifier(model_path=args.model_path)
    tests = read_jsonl(args.tests_path)

    results = []
    correct = 0

    for item in tests:
        text = str(item["text"])
        normalized_text = normalizer.normalize(text)
        expected = str(item.get("expected_skill", item.get("expected_skill_id", "unknown")))
        prediction = classifier.predict(normalized_text)
        ok = prediction.skill == expected
        if ok:
            correct += 1

        results.append({
            "text": text,
            "normalized_text": normalized_text,
            "expected_skill": expected,
            "predicted_skill": prediction.skill,
            "confidence": prediction.confidence,
            "source": prediction.source,
            "ok": ok,
        })

    summary = {
        "model_path": str(args.model_path),
        "model_exists": args.model_path.exists(),
        "total": len(tests),
        "correct": correct,
        "accuracy": correct / len(tests) if tests else 0.0,
        "errors": [row for row in results if not row["ok"]],
        "results": results,
    }

    args.results_path.parent.mkdir(parents=True, exist_ok=True)
    args.results_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "model_exists": summary["model_exists"],
        "total": summary["total"],
        "correct": summary["correct"],
        "accuracy": round(summary["accuracy"], 4),
        "errors_count": len(summary["errors"]),
        "results_path": str(args.results_path),
    }, ensure_ascii=False, indent=2))

    # Fail only when accuracy drops below the minimum acceptable threshold.
    # Individual phrase misclassifications are expected after adding new user
    # apps whose names overlap with window_control / window_layout vocabulary.
    MIN_ACCURACY = 0.98
    passed = summary["accuracy"] >= MIN_ACCURACY

    if summary["errors"]:
        print("\nErrors:")
        for error in summary["errors"][:30]:
            print(
                f"- {error['text']!r}: expected={error['expected_skill']}, "
                f"got={error['predicted_skill']}, source={error['source']}"
            )

    if not passed:
        print(
            f"\nFAIL: accuracy {summary['accuracy']:.4f} < threshold {MIN_ACCURACY}",
            file=sys.stderr,
        )

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
