from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from python_agent.ml_models.skill_classifier_model import SkillClassifierModel
from python_agent.nlu.normalizer import Normalizer


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_PATH = PROJECT_ROOT / "python_agent" / "data" / "skill_classifier" / "processed" / "skill_train.csv"
DEFAULT_MODEL_PATH = PROJECT_ROOT / "python_agent" / "models" / "skill_classifier.joblib"
DEFAULT_METRICS_PATH = PROJECT_ROOT / "python_agent" / "data" / "skill_classifier" / "eval" / "train_metrics.json"


def make_model(random_state: int) -> Pipeline:
    return Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(2, 5),
                    min_df=1,
                    sublinear_tf=True,
                    lowercase=True,
                ),
            ),
            (
                "clf",
                SGDClassifier(
                    loss="log_loss",
                    alpha=1e-5,
                    max_iter=2000,
                    tol=1e-4,
                    class_weight="balanced",
                    random_state=random_state,
                ),
            ),
        ]
    )


def load_training_data(path: Path) -> pd.DataFrame:
    normalizer = Normalizer()
    df = pd.read_csv(path)
    label_column = "skill" if "skill" in df.columns else "skill_id"
    if label_column not in df.columns:
        raise ValueError("Training CSV must contain either skill or skill_id column")

    df["raw_text"] = df["text"].astype(str)
    df["text"] = df["raw_text"].map(normalizer.normalize)
    df["skill"] = df[label_column].astype(str)
    df = df[df["text"].str.len() > 0].copy()

    conflicts = df.groupby("text")["skill"].nunique()
    conflict_texts = conflicts[conflicts > 1]
    if not conflict_texts.empty:
        examples = ", ".join(repr(text) for text in conflict_texts.index[:10])
        raise ValueError(f"Conflicting skill labels after normalization: {examples}")

    return df


def main() -> int:
    parser = argparse.ArgumentParser(description="Train top-level skill classifier")
    parser.add_argument("--data-path", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--metrics-path", type=Path, default=DEFAULT_METRICS_PATH)
    parser.add_argument("--min-confidence", type=float, default=0.50)
    parser.add_argument("--test-size", type=float, default=0.25)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    df = load_training_data(args.data_path)
    y = df["skill"]
    stratify = y if y.value_counts().min() >= 2 else None

    train_df, valid_df = train_test_split(
        df,
        test_size=args.test_size,
        random_state=args.random_state,
        stratify=stratify,
    )

    estimator = make_model(args.random_state)
    estimator.fit(train_df["text"].tolist(), train_df["skill"].tolist())

    y_true = valid_df["skill"].tolist()
    y_pred = estimator.predict(valid_df["text"].tolist())

    metrics: dict[str, Any] = {
        "rows_total": int(len(df)),
        "rows_train": int(len(train_df)),
        "rows_valid": int(len(valid_df)),
        "text_is_normalized": True,
        "classes": sorted(df["skill"].unique().tolist()),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro")),
        "weighted_f1": float(f1_score(y_true, y_pred, average="weighted")),
        "classification_report": classification_report(y_true, y_pred, output_dict=True, zero_division=0),
    }

    wrapper = SkillClassifierModel(estimator=estimator, min_confidence=args.min_confidence)

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
        "classes": metrics["classes"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
