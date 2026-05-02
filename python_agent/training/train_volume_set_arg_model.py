from __future__ import annotations

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
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from python_agent.ml_models.volume_set_arg_model import VolumeSetArgModel


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "python_agent" / "data" / "volume_set" / "processed"
EVAL_DIR = PROJECT_ROOT / "python_agent" / "data" / "volume_set" / "eval"
MODEL_PATH = PROJECT_ROOT / "python_agent" / "models" / "volume_set_arg_model.joblib"
METRICS_PATH = EVAL_DIR / "train_metrics.json"

RANDOM_STATE = 42


def make_text_model() -> Pipeline:
    return Pipeline([
        (
            "tfidf",
            TfidfVectorizer(
                analyzer="char_wb",
                ngram_range=(2, 5),
                min_df=1,
                sublinear_tf=True,
            ),
        ),
        (
            "clf",
            SGDClassifier(
                loss="log_loss",
                alpha=2e-5,
                max_iter=600,
                tol=5e-3,
                random_state=RANDOM_STATE,
                class_weight="balanced",
                n_jobs=-1,
            ),
        ),
    ])


def train_eval(
    df: pd.DataFrame,
    text_col: str,
    label_col: str,
    name: str,
) -> tuple[Pipeline, dict[str, Any]]:
    X = df[text_col].astype(str)
    y = df[label_col].astype(str)
    stratify = y if y.value_counts().min() >= 2 else None

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=RANDOM_STATE,
        stratify=stratify,
    )

    model = make_text_model()
    model.fit(X_train, y_train)

    pred = model.predict(X_test)
    report = classification_report(y_test, pred, output_dict=True, zero_division=0)

    metrics = {
        "name": name,
        "accuracy": float(accuracy_score(y_test, pred)),
        "macro_f1": float(report["macro avg"]["f1-score"]),
        "weighted_f1": float(report["weighted avg"]["f1-score"]),
        "train_samples": int(len(X_train)),
        "test_samples": int(len(X_test)),
        "classes": int(y.nunique()),
    }

    return model, metrics


def read_csv(name: str) -> pd.DataFrame:
    path = DATA_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Missing dataset: {path}")
    return pd.read_csv(path)


def main() -> int:
    action_df = read_csv("action_train.csv")
    value_df = read_csv("value_train.csv")
    vague_df = read_csv("vague_train.csv")

    action_model, action_metrics = train_eval(action_df, "text", "action", "action_model")
    value_model, value_metrics = train_eval(value_df, "text", "value", "value_model")
    vague_model, vague_metrics = train_eval(vague_df, "text", "vague_label", "vague_model")

    model = VolumeSetArgModel(
        action_model=action_model,
        value_model=value_model,
        vague_model=vague_model,
        min_confidence=0.45,
        min_value_confidence=0.05,
    )

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)

    metrics = {
        "model_path": str(MODEL_PATH),
        "dataset_dir": str(DATA_DIR),
        "random_state": RANDOM_STATE,
        "metrics": [action_metrics, value_metrics, vague_metrics],
    }

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
