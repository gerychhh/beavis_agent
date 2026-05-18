from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class WebOpenArgModel:
    """
    Runtime wrapper for the web_open site argument model.

    The model predicts only site_id. Direct URLs stay rule-parsed by
    WebOpenExtractor because URLs are open-ended and should not be guessed.
    """

    estimator: Any
    min_confidence: float = 0.58
    unknown_label: str = "unknown"

    def predict(self, texts: list[str]) -> list[dict]:
        if not isinstance(texts, list):
            raise TypeError("WebOpenArgModel.predict expects list[str]")

        if not texts:
            return []

        predicted = self.estimator.predict(texts)
        confidences = self._confidence(texts, predicted)

        results: list[dict] = []
        for label, conf in zip(predicted, confidences):
            label = str(label)
            conf = float(conf)

            if label == self.unknown_label or conf < self.min_confidence:
                results.append({"missing": ["site_id"], "confidence": round(conf, 4)})
            else:
                results.append({"site_id": label, "confidence": round(conf, 4)})

        return results

    def _confidence(self, texts: list[str], predicted: list[str]) -> list[float]:
        if hasattr(self.estimator, "predict_proba"):
            try:
                proba = self.estimator.predict_proba(texts)
                classes = list(getattr(self.estimator, "classes_", []))
                out: list[float] = []

                for i, label in enumerate(predicted):
                    if label in classes:
                        label_idx = classes.index(label)
                        out.append(float(proba[i][label_idx]))
                    else:
                        out.append(float(max(proba[i])))

                return out
            except Exception:
                pass

        return [0.0 for _ in texts]
