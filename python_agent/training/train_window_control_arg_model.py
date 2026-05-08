from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import joblib
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from python_agent.ml_models.window_control_arg_model import WindowControlArgModel
from python_agent.nlu.normalizer import Normalizer


def make_pipeline() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(2, 5),
            min_df=1,
            sublinear_tf=True,
        )),
        ("clf", SGDClassifier(
            loss="log_loss",
            alpha=1e-5,
            max_iter=2000,
            tol=1e-4,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )),
    ])


def main() -> None:
    data_dir = ROOT / "python_agent" / "data" / "window_control" / "processed"
    eval_dir = ROOT / "python_agent" / "data" / "window_control" / "eval"
    models_dir = ROOT / "python_agent" / "models"

    eval_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    normalizer = Normalizer()

    action_df = pd.read_csv(data_dir / "action_train.csv")
    target_df = pd.read_csv(data_dir / "target_train.csv")

    if len(action_df) != len(target_df):
        raise RuntimeError("action_train.csv and target_train.csv must have the same number of rows")

    df = pd.DataFrame({
        "raw_text": action_df["text"].astype(str),
        "action": action_df["action"].astype(str),
        "target": target_df["target"].astype(str),
    })
    df["text"] = df["raw_text"].map(normalizer.normalize)
    df = df[df["text"].str.len() > 0].copy()

    conflicts = df.groupby("text")[["action", "target"]].nunique()
    conflict_texts = conflicts[(conflicts["action"] > 1) | (conflicts["target"] > 1)]
    if not conflict_texts.empty:
        examples = ", ".join(repr(text) for text in conflict_texts.index[:10])
        raise ValueError(f"Conflicting window_control labels after normalization: {examples}")

    X = df["text"].tolist()
    y_action = df["action"].tolist()
    y_target = df["target"].tolist()

    # Use stratify only when every target class has >= 2 samples.
    indices = list(range(len(X)))
    target_counts = pd.Series(y_target).value_counts()
    can_stratify = int(target_counts.min()) >= 2
    train_idx, val_idx = train_test_split(
        indices,
        test_size=0.2,
        random_state=42,
        stratify=y_target if can_stratify else None,
    )

    X_train = [X[i] for i in train_idx]
    X_val = [X[i] for i in val_idx]

    y_action_train = [y_action[i] for i in train_idx]
    y_action_val = [y_action[i] for i in val_idx]

    y_target_train = [y_target[i] for i in train_idx]
    y_target_val = [y_target[i] for i in val_idx]

    def _fit_model(X_tr: list, y_tr: list) -> object:
        if len(set(y_tr)) < 2:
            clf = DummyClassifier(strategy="most_frequent")
            clf.fit([[0]] * len(y_tr), y_tr)
            return clf
        m = make_pipeline()
        m.fit(X_tr, y_tr)
        return m

    start = time.time()
    action_model = _fit_model(X_train, y_action_train)
    target_model = _fit_model(X_train, y_target_train)
    train_seconds = time.time() - start

    pred_action = action_model.predict(X_val)
    pred_target = target_model.predict(X_val)

    metrics = {
        "dataset_rows": len(X),
        "train_rows": len(X_train),
        "validation_rows": len(X_val),
        "train_seconds": round(train_seconds, 2),
        "action": {
            "accuracy": float(accuracy_score(y_action_val, pred_action)),
            "macro_f1": float(f1_score(y_action_val, pred_action, average="macro")),
            "weighted_f1": float(f1_score(y_action_val, pred_action, average="weighted")),
            "classes": sorted(set(y_action)),
        },
        "target": {
            "accuracy": float(accuracy_score(y_target_val, pred_target)),
            "macro_f1": float(f1_score(y_target_val, pred_target, average="macro")),
            "weighted_f1": float(f1_score(y_target_val, pred_target, average="weighted")),
            "num_classes": len(set(y_target)),
        },
    }

    metadata = {
        "skill": "window_control",
        "version": "0.1.0",
        "model_type": "sklearn Pipeline x2: action_model + target_model",
        "actions": sorted(set(y_action)),
        "target_classes": len(set(y_target)),
        "dataset_rows": len(X),
        "text_is_normalized": True,
        "notes": [
            "Runtime wrapper has no internal normalizer.",
            "Runtime wrapper has no hardcoded app aliases.",
            "All phrase variants are generated into dataset.",
        ],
    }

    model = WindowControlArgModel(
        action_model=action_model,
        target_model=target_model,
        action_threshold=0.35,
        target_threshold=0.03,
        metadata=metadata,
    )

    joblib.dump(model, models_dir / "window_control_arg_model.joblib")

    (eval_dir / "train_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
