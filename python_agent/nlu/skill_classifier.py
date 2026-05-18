from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import warnings

from python_agent.core.schemas import SkillPrediction


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "python_agent" / "models" / "skill_classifier.joblib"
DEFAULT_ALLOWED_SKILLS = {
    "open_app",
    "volume_set",
    "web_open",
    "web_search",
    "window_control",
    "window_layout",
    "unknown",
}


class ModelSkillClassifier:
    def __init__(
        self,
        model_path: str | Path | None = None,
        enabled: bool = True,
        allowed_skills: set[str] | None = None,
    ) -> None:
        self.model_path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        if not self.model_path.is_absolute():
            self.model_path = PROJECT_ROOT / self.model_path

        self.enabled = enabled
        self.allowed_skills = allowed_skills or DEFAULT_ALLOWED_SKILLS
        self._model: Any | None = None

    def predict(self, text: str) -> SkillPrediction:
        if not text.strip():
            return SkillPrediction(skill="unknown", confidence=0.0, source="empty_text")

        if not self.enabled:
            raise RuntimeError("Skill classifier model is disabled")

        if not self.model_path.exists():
            raise FileNotFoundError(f"Skill classifier model not found: {self.model_path}")

        try:
            model = self._load_model()
            prediction = model.predict([text])[0]
        except Exception as error:
            raise RuntimeError(
                f"Skill classifier model failed: {type(error).__name__}: {error}"
            ) from error

        parsed = self._coerce_prediction(prediction)
        skill = parsed.get("skill", "unknown")
        confidence = parsed.get("confidence", 0.0)
        if confidence == 0.0 and skill != "unknown":
            confidence = self._predict_confidence(model, text, skill)

        if skill not in self.allowed_skills:
            raise RuntimeError(f"Model returned invalid skill: {skill}")

        if skill == "unknown":
            return SkillPrediction(skill="unknown", confidence=confidence, source="model_joblib")

        return SkillPrediction(skill=skill, confidence=confidence, source="model_joblib")

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model

        try:
            import joblib
        except ImportError as error:
            raise RuntimeError("joblib is required to load skill classifier models") from error

        with warnings.catch_warnings():
            try:
                from sklearn.exceptions import InconsistentVersionWarning

                warnings.simplefilter("ignore", InconsistentVersionWarning)
            except Exception:
                pass

            self._model = joblib.load(self.model_path)

        return self._model

    def _coerce_prediction(self, prediction: Any) -> dict[str, Any]:
        payload = self._coerce_payload(prediction)
        if isinstance(payload, dict):
            if "missing" in payload:
                missing = payload.get("missing")
                if isinstance(missing, list) and ("skill" in missing or "skill_id" in missing):
                    return {"skill": "unknown", "confidence": self._coerce_confidence(payload.get("confidence"))}

            skill = payload.get("skill", payload.get("skill_id", payload.get("label", payload.get("class", "unknown"))))
            return {
                "skill": str(skill),
                "confidence": self._coerce_confidence(payload.get("confidence")),
            }

        if isinstance(payload, str):
            return {"skill": payload, "confidence": 0.0}

        return {"skill": "unknown", "confidence": 0.0}

    def _coerce_payload(self, prediction: Any) -> Any:
        if isinstance(prediction, dict):
            return prediction

        if isinstance(prediction, str):
            stripped = prediction.strip()
            if not stripped:
                return None

            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return stripped

        return prediction

    def _coerce_confidence(self, value: Any) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.0

        return max(0.0, min(1.0, confidence))

    def _predict_confidence(self, model: Any, text: str, skill: str) -> float:
        predict_proba = getattr(model, "predict_proba", None)
        if predict_proba is None:
            return 0.0

        try:
            probabilities = predict_proba([text])[0]
            classes = list(getattr(model, "classes_", []))
            if skill in classes:
                return self._coerce_confidence(probabilities[classes.index(skill)])
            return self._coerce_confidence(max(probabilities))
        except Exception:
            return 0.0
