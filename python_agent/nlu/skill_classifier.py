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
    "window_control",
    "window_layout",
    "unknown",
}


class RuleSkillClassifier:
    def __init__(self) -> None:
        self.open_app_keywords = {
            "открой",
            "открыть",
            "открывай",
            "запусти",
            "запустить",
            "включи",
            "включить",
            "стартуй",
            "старт",
            "open",
            "run",
            "launch",
        }
        self.non_open_keywords = {
            "закрой",
            "закрыть",
            "сверни",
            "свернуть",
            "close",
            "minimize",
        }
        self.window_control_keywords = {
            "\u0437\u0430\u043a\u0440\u043e\u0439",
            "\u0437\u0430\u043a\u0440\u044b\u0442\u044c",
            "\u0437\u0430\u043a\u0440\u044b\u0432\u0430\u0439",
            "\u0437\u0430\u043a\u0442\u043d\u0438",
            "\u0441\u0432\u0435\u0440\u043d\u0438",
            "\u0441\u0432\u0435\u0440\u043d\u0443\u0442\u044c",
            "\u0441\u043f\u0440\u044f\u0447\u044c",
            "\u0440\u0430\u0437\u0432\u0435\u0440\u043d\u0438",
            "\u0440\u0430\u0437\u0432\u0435\u0440\u043d\u0443\u0442\u044c",
            "\u043c\u0430\u043a\u0441\u0438\u043c\u0438\u0437\u0438\u0440\u0443\u0439",
            "\u0432\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u0438",
            "\u0432\u0435\u0440\u043d\u0438",
            "close",
            "minimize",
            "maximize",
            "restore",
            "fullscreen",
        }
        self.window_layout_keywords = {
            "слева",
            "слево",
            "влево",
            "справа",
            "справо",
            "вправо",
            "сверху",
            "снизу",
            "центр",
            "пополам",
            "половину",
            "палавину",
            "экран",
            "сеткой",
            "fullscreen",
        }
        self.volume_keywords = {
            "громкость",
            "звук",
            "музыка",
            "аудио",
            "volume",
            "громче",
            "погромче",
            "тише",
            "потише",
            "убавь",
            "прибавь",
            "добавь",
            "увеличь",
            "уменьши",
            "понизь",
            "повысь",
            "сбавь",
            "приглуши",
            "громко",
            "тихо",
            "слышно",
            "заткнись",
            "зактни",
            "выруби",
            "отключи",
            "комфортно",
            "нормально",
            "максимум",
            "половину",
        }

    def predict(self, text: str) -> SkillPrediction:
        tokens = set(text.split())

        if tokens & self.volume_keywords:
            return SkillPrediction(skill="volume_set", confidence=0.92)

        if tokens & self.window_layout_keywords:
            return SkillPrediction(skill="window_layout", confidence=0.82)

        if tokens & self.window_control_keywords:
            return SkillPrediction(skill="window_control", confidence=0.82)

        if (tokens & self.open_app_keywords) and not (tokens & self.non_open_keywords):
            return SkillPrediction(skill="open_app", confidence=0.82)

        return SkillPrediction(skill="unknown", confidence=0.0)


class ModelSkillClassifier:
    def __init__(
        self,
        model_path: str | Path | None = None,
        enabled: bool = True,
        fallback_classifier: RuleSkillClassifier | None = None,
        allowed_skills: set[str] | None = None,
    ) -> None:
        self.model_path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        if not self.model_path.is_absolute():
            self.model_path = PROJECT_ROOT / self.model_path

        self.enabled = enabled
        self.fallback_classifier = fallback_classifier or RuleSkillClassifier()
        self.allowed_skills = allowed_skills or DEFAULT_ALLOWED_SKILLS
        self._model: Any | None = None

    def predict(self, text: str) -> SkillPrediction:
        if not text.strip():
            return SkillPrediction(skill="unknown", confidence=0.0, source="empty_text")

        if not self.enabled or not self.model_path.exists():
            return self._fallback(text)

        try:
            model = self._load_model()
            prediction = model.predict([text])[0]
        except Exception as error:
            fallback = self._fallback(text)
            return SkillPrediction(
                skill=fallback.skill,
                confidence=fallback.confidence,
                source=f"model_error:{type(error).__name__}->fallback",
            )

        parsed = self._coerce_prediction(prediction)
        skill = parsed.get("skill", "unknown")
        confidence = parsed.get("confidence", 0.0)
        if confidence == 0.0 and skill != "unknown":
            confidence = self._predict_confidence(model, text, skill)

        if skill not in self.allowed_skills:
            fallback = self._fallback(text)
            return SkillPrediction(
                skill=fallback.skill,
                confidence=fallback.confidence,
                source=f"model_invalid_skill:{skill}->fallback",
            )

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

    def _fallback(self, text: str) -> SkillPrediction:
        return self.fallback_classifier.predict(text)
