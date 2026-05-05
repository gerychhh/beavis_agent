from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any

from python_agent.core.schemas import ArgsPrediction
from python_agent.nlu.argument_extractors.base import ArgumentExtractor
from python_agent.resolvers.app_search import AppSearch


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "python_agent" / "models" / "window_layout_arg_model.joblib"
ALLOWED_LAYOUTS = {
    "left_half",
    "right_half",
    "top_half",
    "bottom_half",
    "center",
    "fullscreen",
    "split_2_vertical",
    "split_2_horizontal",
    "grid_2x2",
}


class WindowLayoutModelExtractor(ArgumentExtractor):
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
            return ArgsPrediction(args={}, confidence=0.0, missing=["layout", "targets"], source="model_disabled")

        if not self.model_path.exists():
            return ArgsPrediction(args={}, confidence=0.0, missing=["layout", "targets"], source="model_missing")

        try:
            model = self._load_model()
            prediction = model.predict([text])[0]
        except Exception as error:
            return ArgsPrediction(
                args={},
                confidence=0.0,
                missing=["layout", "targets"],
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
            return ArgsPrediction(args={}, confidence=confidence, missing=["layout", "targets"], source="model_invalid_output")

        layout = payload.get("layout")
        missing = payload.get("missing")
        args: dict[str, Any] = {}

        if isinstance(layout, str) and layout in ALLOWED_LAYOUTS:
            args["layout"] = layout

        if isinstance(missing, list) and missing:
            if "layout" in args and "targets" in missing:
                matches = self.app_search.find_app_ids_in_text(
                    text,
                    limit=self._required_target_count(args["layout"]),
                )
                if len(matches) >= self._required_target_count(args["layout"]):
                    args["targets"] = matches[:self._required_target_count(args["layout"])]
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

        if "layout" not in args:
            return ArgsPrediction(args={}, confidence=confidence, missing=["layout"], source="model_invalid_layout")

        targets = payload.get("targets")
        if not isinstance(targets, list):
            return ArgsPrediction(args=args, confidence=confidence, missing=["targets"], source="model_invalid_targets")

        clean_targets = [str(item).strip() for item in targets if str(item).strip()]
        if not clean_targets:
            return ArgsPrediction(args=args, confidence=confidence, missing=["targets"], source="model_empty_targets")

        resolved_targets: list[str] = []
        unresolved_targets = 0

        for target in clean_targets:
            if target == "current":
                resolved_targets.append(target)
                continue

            resolved_app_id = self.app_search.resolve_app_id(target)
            if resolved_app_id is None:
                unresolved_targets += 1
                continue

            if resolved_app_id not in resolved_targets:
                resolved_targets.append(resolved_app_id)

        if unresolved_targets:
            for app_id in self.app_search.find_app_ids_in_text(text, limit=len(clean_targets)):
                if app_id not in resolved_targets:
                    resolved_targets.append(app_id)

        if len(resolved_targets) < len(clean_targets):
            return ArgsPrediction(
                args=args,
                confidence=confidence,
                missing=["targets"],
                source="model_unknown_app_target",
            )

        args["targets"] = resolved_targets
        return ArgsPrediction(args=args, confidence=confidence, missing=[], source="model_joblib")

    def _required_target_count(self, layout: str) -> int:
        if layout in {"split_2_vertical", "split_2_horizontal"}:
            return 2
        if layout == "grid_2x2":
            return 4
        return 1

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
