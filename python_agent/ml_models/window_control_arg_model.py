from __future__ import annotations

from typing import Any
import math


class WindowControlArgModel:
    def __init__(
        self,
        action_model: Any,
        target_model: Any,
        action_threshold: float = 0.35,
        target_threshold: float = 0.03,
        metadata: dict | None = None,
    ) -> None:
        self.action_model = action_model
        self.target_model = target_model
        self.action_threshold = float(action_threshold)
        self.target_threshold = float(target_threshold)
        self.metadata = metadata or {}

    def predict(self, texts: list[str]) -> list[dict]:
        texts = [str(text) for text in texts]

        action_pred = self.action_model.predict(texts)
        target_pred = self.target_model.predict(texts)

        action_conf = self._max_proba(self.action_model, texts)
        target_conf = self._max_proba(self.target_model, texts)

        results: list[dict] = []

        for action, target, a_conf, t_conf in zip(action_pred, target_pred, action_conf, target_conf):
            action = str(action)
            target = str(target)
            confidence = float(min(a_conf, t_conf))

            if action == "unknown" or a_conf < self.action_threshold:
                results.append({
                    "missing": ["action"],
                    "confidence": round(float(a_conf), 4),
                })
                continue

            if target == "unknown" or t_conf < self.target_threshold:
                results.append({
                    "action": action,
                    "missing": ["target"],
                    "confidence": round(confidence, 4),
                })
                continue

            if target == "current":
                results.append({
                    "action": action,
                    "target_type": "current",
                    "confidence": round(confidence, 4),
                })
            else:
                results.append({
                    "action": action,
                    "target_type": "app",
                    "app_id": target,
                    "confidence": round(confidence, 4),
                })

        return results

    def _max_proba(self, model: Any, texts: list[str]) -> list[float]:
        if not hasattr(model, "predict_proba"):
            return [0.0 for _ in texts]

        proba = model.predict_proba(texts)
        result: list[float] = []

        for row in proba:
            try:
                max_value = float(max(row))
            except Exception:
                max_value = 0.0

            if math.isnan(max_value):
                max_value = 0.0

            result.append(max_value)

        return result
