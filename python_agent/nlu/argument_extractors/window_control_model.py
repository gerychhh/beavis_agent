from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any

from python_agent.core.schemas import ArgsPrediction
from python_agent.nlu.argument_extractors.base import ArgumentExtractor
from python_agent.resolvers.app_search import AppSearch


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "python_agent" / "models" / "window_control_arg_model.joblib"
ALLOWED_ACTIONS = {"close", "minimize", "maximize", "restore"}
ALLOWED_TARGET_TYPES = {"current", "app"}


class WindowControlModelExtractor(ArgumentExtractor):
    def __init__(
        self,
        model_path: str | Path | None = None,
        enabled: bool = True,
        app_search: AppSearch | None = None,
    ) -> None:
        self.model_path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        if not self.model_path.is_absolute():
            self.model_path = PROJECT_ROOT / self.model_path

        self.enabled = enabled
        self.app_search = app_search or AppSearch()
        self._model: Any | None = None

    def extract(self, text: str) -> ArgsPrediction:
        if not self.enabled:
            return ArgsPrediction(args={}, confidence=0.0, missing=["action"], source="model_disabled")

        if not self.model_path.exists():
            return ArgsPrediction(args={}, confidence=0.0, missing=["action"], source="model_missing")

        try:
            model = self._load_model()
            prediction = model.predict([text])[0]
        except Exception as error:
            return ArgsPrediction(
                args={},
                confidence=0.0,
                missing=["action"],
                source=f"model_error:{type(error).__name__}",
            )

        return self._coerce_prediction(prediction, text)

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

    def _coerce_prediction(self, prediction: Any, text: str) -> ArgsPrediction:
        payload = self._coerce_payload(prediction)
        confidence = self._extract_confidence(payload)

        if not isinstance(payload, dict):
            return ArgsPrediction(args={}, confidence=confidence, missing=["action"], source="model_invalid_output")

        missing = payload.get("missing")
        if isinstance(missing, list) and missing:
            action = payload.get("action")
            args = {}
            if isinstance(action, str) and action in ALLOWED_ACTIONS:
                args["action"] = action
                if "target" in missing:
                    matches = self.app_search.find_app_ids_in_text(text, limit=1)
                    if matches:
                        args["target_type"] = "app"
                        args["app_id"] = matches[0]
                        return ArgsPrediction(
                            args=args,
                            confidence=confidence,
                            missing=[],
                            source="model_joblib_app_search",
                        )

            return ArgsPrediction(
                args=args,
                confidence=confidence,
                missing=[str(item) for item in missing],
                source="model_joblib_missing",
            )

        action = payload.get("action")
        if not isinstance(action, str) or action not in ALLOWED_ACTIONS:
            return ArgsPrediction(args={}, confidence=confidence, missing=["action"], source="model_invalid_action")

        target_type = payload.get("target_type")
        if not isinstance(target_type, str) or target_type not in ALLOWED_TARGET_TYPES:
            return ArgsPrediction(
                args={"action": action},
                confidence=confidence,
                missing=["target"],
                source="model_invalid_target",
            )

        args: dict[str, Any] = {
            "action": action,
            "target_type": target_type,
        }

        if target_type == "app":
            app_id = payload.get("app_id")
            if not isinstance(app_id, str) or not app_id.strip() or app_id == "unknown":
                return ArgsPrediction(
                    args={"action": action},
                    confidence=confidence,
                    missing=["target"],
                    source="model_invalid_app_id",
                )

            resolved_app_id = self.app_search.resolve_app_id(app_id)
            if resolved_app_id is None:
                matches = self.app_search.find_app_ids_in_text(text, limit=1)
                resolved_app_id = matches[0] if matches else None

            if resolved_app_id is None:
                return ArgsPrediction(
                    args={"action": action},
                    confidence=confidence,
                    missing=["target"],
                    source="model_unknown_app_target",
                )
            args["app_id"] = resolved_app_id

        return ArgsPrediction(args=args, confidence=confidence, missing=[], source="model_joblib")

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
