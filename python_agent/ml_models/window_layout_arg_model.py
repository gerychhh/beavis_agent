from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class WindowLayoutArgModel:
    """
    Runtime wrapper for window_layout argument extraction.

    IMPORTANT:
    - No text normalization here.
    - No hardcoded aliases here.
    - No phrase if/else shortcuts here.
    - All linguistic knowledge must come from the training dataset.
    """

    vectorizer: Any
    layout_model: Any
    target_models: list[Any]
    metadata: dict[str, Any] | None = None
    layout_threshold: float = 0.35
    target_threshold: float = 0.12
    target_fill_threshold: float = 0.035

    def predict(self, texts: list[str]) -> list[dict]:
        if not texts:
            return []

        x = self.vectorizer.transform([str(t) for t in texts])
        layout_preds = self.layout_model.predict(x)
        layout_probas = self._safe_predict_proba(self.layout_model, x)

        target_preds = [model.predict(x) for model in self.target_models]
        target_probas = [self._safe_predict_proba(model, x) for model in self.target_models]

        results: list[dict] = []

        for i, _ in enumerate(texts):
            layout = str(layout_preds[i])
            layout_conf = self._pred_conf(self.layout_model, layout_probas, i, layout)

            if layout == "unknown" or layout_conf < self.layout_threshold:
                results.append({
                    "missing": ["layout", "targets"],
                    "confidence": round(float(layout_conf), 4),
                })
                continue

            required_targets = self._required_target_count(layout)
            max_targets = self._max_target_count(layout)

            targets: list[str] = []
            target_confs: list[float] = []

            # Main ordered slot predictions.
            for slot_idx, model in enumerate(self.target_models):
                target = str(target_preds[slot_idx][i])
                conf = self._pred_conf(model, target_probas[slot_idx], i, target)
                if target != "NO_TARGET" and conf >= self.target_threshold and target not in targets:
                    targets.append(target)
                    target_confs.append(float(conf))
                if len(targets) >= max_targets:
                    break

            # Generic probability-based fill for multi-target layouts.
            # This is not a phrase parser; it only uses the trained target models' probabilities.
            if required_targets > 1 and len(targets) < required_targets:
                candidates: list[tuple[int, float, str]] = []
                for slot_idx, model in enumerate(self.target_models):
                    proba = target_probas[slot_idx]
                    if proba is None:
                        continue
                    row = proba[i]
                    order = np.argsort(row)[::-1]
                    for class_idx in order[:8]:
                        cls = str(model.classes_[class_idx])
                        conf = float(row[class_idx])
                        if cls == "NO_TARGET" or cls in targets:
                            continue
                        if conf >= self.target_fill_threshold:
                            candidates.append((slot_idx, conf, cls))

                # Preserve slot order first, confidence second.
                candidates.sort(key=lambda item: (item[0], -item[1]))
                for _, conf, cls in candidates:
                    if cls not in targets:
                        targets.append(cls)
                        target_confs.append(float(conf))
                    if len(targets) >= required_targets:
                        break

            if len(targets) < required_targets:
                results.append({
                    "layout": layout,
                    "missing": ["targets"],
                    "confidence": round(float(layout_conf), 4),
                })
                continue

            targets = targets[:max_targets]
            confidence_parts = [float(layout_conf)] + target_confs[:len(targets)]
            confidence = float(np.mean(confidence_parts)) if confidence_parts else float(layout_conf)

            results.append({
                "layout": layout,
                "targets": targets,
                "confidence": round(confidence, 4),
            })

        return results

    def _required_target_count(self, layout: str) -> int:
        if layout in {"split_2_vertical", "split_2_horizontal"}:
            return 2
        if layout == "grid_2x2":
            return 4
        if layout in {"fullscreen", "left_half", "right_half", "top_half", "bottom_half", "center"}:
            return 1
        return 1

    def _max_target_count(self, layout: str) -> int:
        if layout in {"split_2_vertical", "split_2_horizontal"}:
            return 2
        if layout == "grid_2x2":
            return 4
        return 1

    def _safe_predict_proba(self, model: Any, x: Any):
        if hasattr(model, "predict_proba"):
            return model.predict_proba(x)
        return None

    def _pred_conf(self, model: Any, proba, row_idx: int, pred: str) -> float:
        if proba is None:
            return 0.70
        classes = list(map(str, model.classes_))
        try:
            idx = classes.index(str(pred))
        except ValueError:
            return 0.0
        return float(proba[row_idx][idx])
