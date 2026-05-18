from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import warnings

from python_agent.core.schemas import ArgsPrediction
from python_agent.nlu.argument_extractors.base import ArgumentExtractor
from python_agent.nlu.normalizer import Normalizer


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "python_agent" / "models" / "web_open_arg_model.joblib"


class WebOpenModelExtractor(ArgumentExtractor):
    def __init__(
        self,
        model_path: str | Path | None = None,
        normalizer: Normalizer | None = None,
        enabled: bool = True,
    ) -> None:
        self.model_path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        if not self.model_path.is_absolute():
            self.model_path = PROJECT_ROOT / self.model_path

        self.normalizer = normalizer or Normalizer()
        self.enabled = enabled
        self._model: Any | None = None

    def extract(self, text: str) -> ArgsPrediction:
        if not self.enabled:
            return ArgsPrediction(args={}, confidence=0.0, missing=["site_id"], source="web_model_disabled")

        if not self.model_path.exists():
            return ArgsPrediction(args={}, confidence=0.0, missing=["site_id"], source="web_model_missing")

        try:
            model = self._load_model()
            normalized = self.normalizer.normalize(text)
            prediction = model.predict([normalized])[0]
        except Exception as error:
            return ArgsPrediction(
                args={},
                confidence=0.0,
                missing=["site_id"],
                source=f"web_model_error:{type(error).__name__}",
            )

        return self._coerce_prediction(prediction)

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

    def _coerce_prediction(self, prediction: Any) -> ArgsPrediction:
        payload = self._coerce_payload(prediction)
        confidence = self._extract_confidence(payload)

        if isinstance(payload, dict):
            missing = payload.get("missing")
            if isinstance(missing, list) and missing:
                return ArgsPrediction(
                    args={},
                    confidence=confidence,
                    missing=[str(item) for item in missing],
                    source="web_model_missing",
                )

            site_id = payload.get("site_id")
            if isinstance(site_id, str) and site_id.strip() and site_id != "unknown":
                return ArgsPrediction(
                    args={"site_id": site_id.strip()},
                    confidence=confidence,
                    missing=[],
                    source="web_model_joblib",
                )

        if isinstance(payload, str) and payload.strip() and payload != "unknown":
            return ArgsPrediction(
                args={"site_id": payload.strip()},
                confidence=confidence,
                missing=[],
                source="web_model_legacy",
            )

        return ArgsPrediction(args={}, confidence=confidence, missing=["site_id"], source="web_model_invalid_output")

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

    def _extract_confidence(self, payload: Any) -> float:
        if isinstance(payload, dict) and "confidence" in payload:
            try:
                return float(payload["confidence"])
            except (TypeError, ValueError):
                pass

        return 0.0
