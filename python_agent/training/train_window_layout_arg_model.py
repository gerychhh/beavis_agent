from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import FeatureUnion

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from python_agent.ml_models.window_layout_arg_model import WindowLayoutArgModel


DATA_PATH = ROOT / "python_agent" / "data" / "window_layout" / "processed" / "window_layout_train.csv"
MODEL_PATH = ROOT / "python_agent" / "models" / "window_layout_arg_model.joblib"
METRICS_PATH = ROOT / "python_agent" / "data" / "window_layout" / "eval" / "train_metrics.json"


def make_vectorizer() -> FeatureUnion:
    return FeatureUnion([
        ("char", TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(2, 5),
            min_df=1,
            max_features=30000,
        )),
        ("word", TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 4),
            min_df=1,
            max_features=30000,
        )),
    ])


def make_classifier() -> SGDClassifier:
    return SGDClassifier(
        loss="log_loss",
        alpha=1e-5,
        max_iter=22,
        tol=1e-3,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )


def train_one(col: str, x_train_vec, x_test_vec, train_df, test_df):
    model = make_classifier()
    y_train = train_df[col].astype(str)
    y_test = test_df[col].astype(str)

    model.fit(x_train_vec, y_train)
    pred = model.predict(x_test_vec)

    metrics = {
        "accuracy": float(accuracy_score(y_test, pred)),
        "macro_f1": float(f1_score(y_test, pred, average="macro")),
        "weighted_f1": float(f1_score(y_test, pred, average="weighted")),
        "classes": sorted(map(str, set(y_train) | set(y_test))),
    }
    return model, metrics


def main():
    df = pd.read_csv(DATA_PATH)

    train_df, test_df = train_test_split(
        df,
        test_size=0.20,
        random_state=42,
        stratify=df["layout"],
    )

    x_train = train_df["text"].astype(str).tolist()
    x_test = test_df["text"].astype(str).tolist()

    vectorizer = make_vectorizer()
    x_train_vec = vectorizer.fit_transform(x_train)
    x_test_vec = vectorizer.transform(x_test)

    layout_model, layout_metrics = train_one("layout", x_train_vec, x_test_vec, train_df, test_df)

    target_models = []
    target_metrics = {}
    for col in ["target_1", "target_2", "target_3", "target_4"]:
        target_model, metrics = train_one(col, x_train_vec, x_test_vec, train_df, test_df)
        target_models.append(target_model)
        target_metrics[col] = metrics

    metadata = {
        "skill": "window_layout",
        "version": "0.1.0",
        "dataset_rows": int(len(df)),
        "train_rows": int(len(train_df)),
        "validation_rows": int(len(test_df)),
        "model_type": "FeatureUnion capped(Tfidf char_wb 2-5 max_features=30000 + word 1-4 max_features=30000) + 5 SGDClassifier(log_loss)",
        "runtime_rules": "none",
        "normalizer_inside_model": False,
    }

    wrapper = WindowLayoutArgModel(
        vectorizer=vectorizer,
        layout_model=layout_model,
        target_models=target_models,
        metadata=metadata,
        layout_threshold=0.35,
        target_threshold=0.12,
        target_fill_threshold=0.035,
    )

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(wrapper, MODEL_PATH, compress=3)

    metrics = {
        "layout_model": layout_metrics,
        "target_models": target_metrics,
        "metadata": metadata,
    }

    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "saved_model": str(MODEL_PATH),
        "dataset_rows": len(df),
        "layout_accuracy": layout_metrics["accuracy"],
        "layout_macro_f1": layout_metrics["macro_f1"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
