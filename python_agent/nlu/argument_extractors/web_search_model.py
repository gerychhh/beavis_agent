from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import warnings

from python_agent.core.schemas import ArgsPrediction
from python_agent.nlu.argument_extractors.base import ArgumentExtractor
from python_agent.nlu.normalizer import Normalizer


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "python_agent" / "models" / "web_search_query_extractor.joblib"
LEGACY_MODEL_PATH = PROJECT_ROOT / "python_agent" / "models" / "web_search_query_model.joblib"


class WebSearchModelExtractor(ArgumentExtractor):
    """Optional ML extractor for search query text.

    The preferred model is the v3 hybrid extractor from
    python_agent.ml_models.web_search_query_extractor. It combines deterministic
    span cleanup with a lightweight sklearn no-query/confidence model. The old
    pattern model is still supported as a compatibility fallback.
    """

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
            return ArgsPrediction(args={}, confidence=0.0, missing=["query"], source="web_search_model_disabled")

        if not self.model_path.exists() and self.model_path == DEFAULT_MODEL_PATH:
            self.model_path = LEGACY_MODEL_PATH

        if not self.model_path.exists():
            return ArgsPrediction(args={}, confidence=0.0, missing=["query"], source="web_search_model_missing")

        try:
            model = self._load_model()
            prediction = self._predict(model, text)
        except Exception as error:
            return ArgsPrediction(
                args={},
                confidence=0.0,
                missing=["query"],
                source=f"web_search_model_error:{type(error).__name__}",
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

            if self.model_path.name == "web_search_query_extractor.joblib":
                from python_agent.ml_models.web_search_query_extractor import WebSearchQueryExtractor

                self._model = WebSearchQueryExtractor.load(self.model_path)
            else:
                self._model = joblib.load(self.model_path)
        return self._model

    def _predict(self, model: Any, text: str) -> Any:
        if model.__class__.__name__ == "WebSearchQueryExtractor":
            return model.predict(text)

        normalized = self.normalizer.normalize(text)
        return model.predict([normalized])[0]

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
                    source="web_search_model_missing",
                )

            query = payload.get("query")
            if isinstance(query, str) and query.strip():
                return ArgsPrediction(
                    args={"query": query.strip()},
                    confidence=confidence,
                    missing=[],
                    source="web_search_model_joblib",
                )

        return ArgsPrediction(args={}, confidence=confidence, missing=["query"], source="web_search_model_invalid_output")

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
                return {"query": stripped}

        return prediction

    def _extract_confidence(self, payload: Any) -> float:
        if isinstance(payload, dict) and "confidence" in payload:
            try:
                return float(payload["confidence"])
            except (TypeError, ValueError):
                pass
        return 0.0
