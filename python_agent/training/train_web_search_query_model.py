from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


import joblib
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def sample_rows(rows: list[dict], limit: int, seed: int) -> list[dict]:
    if limit <= 0 or len(rows) <= limit:
        return rows
    rng = random.Random(seed)
    return rng.sample(rows, limit)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-path",
        type=Path,
        default=Path("python_agent/data/web_search/raw/web_search_query_extraction_dataset.jsonl"),
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=Path("python_agent/models/web_search_query_extractor.joblib"),
    )
    parser.add_argument(
        "--metrics-path",
        type=Path,
        default=Path("python_agent/data/web_search/eval/train_metrics.json"),
    )
    parser.add_argument("--train-sample", type=int, default=30000)
    parser.add_argument("--threshold", type=float, default=0.45)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rows = read_jsonl(args.data_path)
    train_rows = sample_rows(rows, args.train_sample, args.seed)
    texts = [str(row.get("text", "")) for row in train_rows]
    labels = [0 if row.get("query") is None else 1 for row in train_rows]

    model = Pipeline([
        ("count", CountVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1, max_features=30000)),
        ("clf", MultinomialNB(alpha=0.05)),
    ])
    model.fit(texts, labels)

    args.model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "threshold": args.threshold,
            "model_name": "multinomial_nb_char",
        },
        args.model_path,
    )

    metrics = {
        "rows_total": len(rows),
        "train_rows": len(train_rows),
        "positive_rows": sum(labels),
        "no_query_rows": len(labels) - sum(labels),
        "model_name": "multinomial_nb_char",
        "threshold": args.threshold,
    }
    args.metrics_path.parent.mkdir(parents=True, exist_ok=True)
    args.metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "model_path": str(args.model_path),
        "metrics_path": str(args.metrics_path),
        **metrics,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
