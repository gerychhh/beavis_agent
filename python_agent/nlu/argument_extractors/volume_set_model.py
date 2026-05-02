from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import warnings

from python_agent.core.schemas import ArgsPrediction
from python_agent.nlu.argument_extractors.base import ArgumentExtractor


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "python_agent" / "models" / "volume_set_arg_model.joblib"


class VolumeSetModelExtractor(ArgumentExtractor):
    def __init__(
        self,
        model_path: str | Path | None = None,
        enabled: bool = True,
        min_percent: int = 0,
        max_percent: int = 100,
        min_delta: int = -100,
        max_delta: int = 100,
    ) -> None:
        self.model_path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        if not self.model_path.is_absolute():
            self.model_path = PROJECT_ROOT / self.model_path

        self.enabled = enabled
        self.min_percent = min_percent
        self.max_percent = max_percent
        self.min_delta = min_delta
        self.max_delta = max_delta
        self._model: Any | None = None

    def extract(self, text: str) -> ArgsPrediction:
        if not self.enabled:
            return ArgsPrediction(args={}, confidence=0.0, missing=["percent"], source="model_disabled")

        if not self.model_path.exists():
            return ArgsPrediction(args={}, confidence=0.0, missing=["percent"], source="model_missing")

        try:
            model = self._load_model()
            prediction = model.predict([text])[0]
        except Exception as error:
            return ArgsPrediction(
                args={},
                confidence=0.0,
                missing=["percent"],
                source=f"model_error:{type(error).__name__}",
            )

        return self._coerce_prediction(prediction, model, text)

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model

        try:
            import joblib
        except ImportError as error:
            raise RuntimeError("joblib is required to load argument models") from error

        with warnings.catch_warnings():
            try:
                from sklearn.exceptions import InconsistentVersionWarning

                warnings.simplefilter("ignore", InconsistentVersionWarning)
            except Exception:
                pass

            self._model = joblib.load(self.model_path)

        return self._model

    def _coerce_prediction(self, prediction: Any, model: Any, text: str) -> ArgsPrediction:
        payload = self._coerce_payload(prediction)
        confidence = self._extract_confidence(payload, model, text)

        if isinstance(payload, dict):
            mode = payload.get("mode")

            if mode == "set":
                percent = self._coerce_int(payload.get("percent"), self.min_percent, self.max_percent)
                if percent is None:
                    return ArgsPrediction(args={}, confidence=0.2, missing=["percent"], source="model_invalid_output")

                return ArgsPrediction(
                    args={"mode": "set", "percent": percent},
                    confidence=confidence,
                    missing=[],
                    source="model_joblib",
                )

            if mode == "delta":
                delta = self._coerce_int(payload.get("delta"), self.min_delta, self.max_delta)
                if delta is None:
                    return ArgsPrediction(args={}, confidence=0.2, missing=["delta"], source="model_invalid_output")

                return ArgsPrediction(
                    args={"mode": "delta", "delta": delta},
                    confidence=confidence,
                    missing=[],
                    source="model_joblib",
                )

            if mode == "missing":
                missing = payload.get("missing")
                if not isinstance(missing, list) or not missing:
                    missing = ["percent"]

                return ArgsPrediction(
                    args={},
                    confidence=confidence,
                    missing=[str(item) for item in missing],
                    source="model_joblib_missing",
                )

            if "percent" in payload:
                percent = self._coerce_int(payload.get("percent"), self.min_percent, self.max_percent)
                if percent is not None:
                    return ArgsPrediction(
                        args={"mode": "set", "percent": percent},
                        confidence=confidence,
                        missing=[],
                        source="model_joblib_legacy",
                    )

        percent = self._coerce_int(payload, self.min_percent, self.max_percent)
        if percent is not None:
            return ArgsPrediction(
                args={"mode": "set", "percent": percent},
                confidence=confidence,
                missing=[],
                source="model_joblib_legacy",
            )

        return ArgsPrediction(args={}, confidence=0.2, missing=["percent"], source="model_invalid_output")

    def _coerce_payload(self, prediction: Any) -> Any:
        if isinstance(prediction, dict):
            return prediction

        if isinstance(prediction, str):
            return self._coerce_from_string(prediction)

        return prediction

    def _coerce_from_string(self, prediction: str) -> Any:
        stripped = prediction.strip()
        if not stripped:
            return None

        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return stripped

        return parsed

    def _coerce_int(self, value: Any, min_value: int, max_value: int) -> int | None:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None

        if min_value <= number <= max_value:
            return number

        return None

    def _extract_confidence(self, payload: Any, model: Any, text: str) -> float:
        if isinstance(payload, dict) and "confidence" in payload:
            try:
                return float(payload["confidence"])
            except (TypeError, ValueError):
                pass

        return self._predict_confidence(model, text)

    def _predict_confidence(self, model: Any, text: str) -> float:
        predict_proba = getattr(model, "predict_proba", None)
        if predict_proba is None:
            return 0.7

        try:
            probabilities = predict_proba([text])[0]
            if isinstance(probabilities, (float, int)):
                return float(probabilities)

            return float(max(probabilities))
        except Exception:
            return 0.7
