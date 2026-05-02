from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SkillClassifierModel:
    """
    Runtime wrapper for the top-level skill classifier.

    IMPORTANT:
    - This class receives already normalized text.
    - This class does not extract skill arguments.
    - This class does not know Windows paths or execute anything.

    Expected output:
      {"skill": "open_app", "confidence": 0.91}

    `ModelSkillClassifier` also accepts older external wrappers that return
    `skill_id`, but new models should use `skill`.
    """

    estimator: Any
    min_confidence: float = 0.50
    unknown_label: str = "unknown"

    def predict(self, texts: list[str]) -> list[dict]:
        if not isinstance(texts, list):
            raise TypeError("SkillClassifierModel.predict expects list[str]")

        if not texts:
            return []

        predicted = self.estimator.predict(texts)
        confidences = self._confidence(texts, predicted)

        results: list[dict] = []
        for label, conf in zip(predicted, confidences):
            skill = str(label)
            confidence = float(conf)

            if skill == self.unknown_label or confidence < self.min_confidence:
                results.append({"skill": self.unknown_label, "confidence": round(confidence, 4)})
            else:
                results.append({"skill": skill, "confidence": round(confidence, 4)})

        return results

    def _confidence(self, texts: list[str], predicted: list[str]) -> list[float]:
        if hasattr(self.estimator, "predict_proba"):
            try:
                proba = self.estimator.predict_proba(texts)
                classes = list(getattr(self.estimator, "classes_", []))
                out: list[float] = []

                for index, label in enumerate(predicted):
                    if label in classes:
                        label_index = classes.index(label)
                        out.append(float(proba[index][label_index]))
                    else:
                        out.append(float(max(proba[index])))

                return out
            except Exception:
                pass

        return [0.0 for _ in texts]
