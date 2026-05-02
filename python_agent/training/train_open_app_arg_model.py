from __future__ import annotations

import argparse
import json
from pathlib import Path

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from python_agent.ml_models.open_app_arg_model import OpenAppArgModel
from python_agent.nlu.normalizer import Normalizer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-path", type=Path, default=Path("python_agent/data/open_app/processed/app_train.csv"))
    parser.add_argument("--model-path", type=Path, default=Path("python_agent/models/open_app_arg_model.joblib"))
    parser.add_argument("--metrics-path", type=Path, default=Path("python_agent/data/open_app/eval/train_metrics.json"))
    parser.add_argument("--min-confidence", type=float, default=0.50)
    parser.add_argument("--test-size", type=float, default=0.20)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    normalizer = Normalizer()

    df = pd.read_csv(args.data_path)
    df["raw_text"] = df["text"].astype(str)
    df["text"] = df["raw_text"].map(normalizer.normalize)
    df["app_id"] = df["app_id"].astype(str)
    df = df[df["text"].str.len() > 0].copy()

    conflicts = df.groupby("text")["app_id"].nunique()
    conflict_texts = conflicts[conflicts > 1]
    if not conflict_texts.empty:
        examples = ", ".join(repr(text) for text in conflict_texts.index[:10])
        raise ValueError(f"Conflicting app_id labels after normalization: {examples}")

    train_df, valid_df = train_test_split(
        df,
        test_size=args.test_size,
        random_state=args.random_state,
        stratify=df["app_id"],
    )

    pipeline = Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(2, 5),
                    min_df=2,
                    max_features=35000,
                    sublinear_tf=True,
                    lowercase=True,
                ),
            ),
            (
                "clf",
                SGDClassifier(
                    loss="log_loss",
                    alpha=1e-5,
                    penalty="l2",
                    max_iter=12,
                    tol=None,
                    class_weight="balanced",
                    random_state=args.random_state,
                    n_jobs=-1,
                ),
            ),
        ]
    )

    pipeline.fit(train_df["text"].tolist(), train_df["app_id"].tolist())

    y_true = valid_df["app_id"].tolist()
    y_pred = pipeline.predict(valid_df["text"].tolist())

    metrics = {
        "rows_total": int(len(df)),
        "rows_train": int(len(train_df)),
        "rows_valid": int(len(valid_df)),
        "text_is_normalized": True,
        "classes": sorted(df["app_id"].unique().tolist()),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro")),
        "weighted_f1": float(f1_score(y_true, y_pred, average="weighted")),
        "classification_report": classification_report(y_true, y_pred, output_dict=True, zero_division=0),
    }

    wrapper = OpenAppArgModel(estimator=pipeline, min_confidence=args.min_confidence)

    args.model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(wrapper, args.model_path)

    args.metrics_path.parent.mkdir(parents=True, exist_ok=True)
    args.metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "model_path": str(args.model_path),
        "metrics_path": str(args.metrics_path),
        "accuracy": round(metrics["accuracy"], 4),
        "macro_f1": round(metrics["macro_f1"], 4),
        "rows_total": metrics["rows_total"],
        "classes_count": len(metrics["classes"]),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
