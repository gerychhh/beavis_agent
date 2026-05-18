from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from python_agent.nlu.argument_extractors.web_search_model import WebSearchModelExtractor
from python_agent.nlu.normalizer import Normalizer


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=Path, default=Path("python_agent/models/web_search_query_extractor.joblib"))
    parser.add_argument("--tests-path", type=Path, default=Path("python_agent/data/web_search/eval/manual_tests.jsonl"))
    parser.add_argument("--results-path", type=Path, default=Path("python_agent/data/web_search/eval/test_results.json"))
    args = parser.parse_args()

    extractor = WebSearchModelExtractor(model_path=args.model_path)
    tests = read_jsonl(args.tests_path)
    normalizer = Normalizer()

    results = []
    correct = 0
    for item in tests:
        text = str(item["text"])
        raw_expected = item.get("expected_query", item.get("query", ""))
        expected = "" if raw_expected is None or str(raw_expected).lower() == "none" else normalizer.normalize(str(raw_expected))
        normalized_text = normalizer.normalize(text)
        prediction = extractor.extract(text)
        got = normalizer.normalize(str(prediction.args.get("query", "")))
        ok = got == expected
        if ok:
            correct += 1
        results.append({
            "text": text,
            "normalized_text": normalized_text,
            "expected_query": expected,
            "prediction": prediction.to_dict(),
            "predicted_query": got,
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
        for error in summary["errors"][:30]:
            print(
                f"- {error['text']!r}: expected={error['expected_query']!r}, "
                f"got={error['predicted_query']!r}, pred={error['prediction']}"
            )


if __name__ == "__main__":
    main()
