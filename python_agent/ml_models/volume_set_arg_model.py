from typing import Any, Dict, List, Optional, Tuple


class VolumeSetArgModel:
    """
    Обертка для skill volume_set.

    Внутри:
    - action_model: text -> set/increase/decrease/mute/unknown
    - value_model: text -> 0..100/NO_VALUE
    - vague_model: text -> DELTA_*/SET_*/UNKNOWN

    Интерфейс:
        model.predict(["убавь на пятьдесят"])
        -> [{"mode": "delta", "delta": -50, "confidence": 0.91}]
    """

    def __init__(
        self,
        action_model,
        value_model,
        vague_model,
        min_confidence: float = 0.45,
        min_value_confidence: float = 0.75,
    ):
        self.action_model = action_model
        self.value_model = value_model
        self.vague_model = vague_model
        self.min_confidence = min_confidence
        self.min_value_confidence = min_value_confidence

    def predict(self, texts: List[str]) -> List[Dict[str, Any]]:
        return [self._predict_one(text) for text in texts]

    def predict_proba(self, texts: List[str]) -> List[float]:
        return [self._predict_one(text).get("confidence", 0.0) for text in texts]

    def _predict_one(self, text: str) -> Dict[str, Any]:
        text = str(text).strip()

        action, action_conf = self._predict_label(self.action_model, text)

        # mute has priority
        if action == "mute":
            return {
                "mode": "set",
                "percent": 0,
                "confidence": round(float(action_conf), 4),
                "debug": {"source": "action_mute", "action": action, "action_conf": round(float(action_conf), 4)},
            }

        # 1) Value model: exact value or NO_VALUE.
        value, value_conf = self._predict_label(self.value_model, text)
        if value != "NO_VALUE" and value_conf >= self.min_value_confidence:
            try:
                number = int(value)
            except Exception:
                number = None

            if number is not None:
                return self._build_from_action_and_value(
                    action=action,
                    action_conf=action_conf,
                    value=number,
                    value_conf=value_conf,
                    source="value_model",
                )

        # 2) Vague model: human relative/soft volume phrases.
        vague, vague_conf = self._predict_label(self.vague_model, text)
        parsed = self._parse_vague_label(vague)

        if parsed is not None:
            parsed["confidence"] = round(float(max(action_conf, vague_conf)), 4)
            parsed["debug"] = {
                "source": "vague_model",
                "action": action,
                "action_conf": round(float(action_conf), 4),
                "value": value,
                "value_conf": round(float(value_conf), 4),
                "vague": vague,
                "vague_conf": round(float(vague_conf), 4),
            }
            return parsed

        return {
            "mode": "missing",
            "missing": ["percent"],
            "confidence": 0.0,
            "debug": self._debug("missing", action, action_conf, value, value_conf, vague, vague_conf),
        }

    def _build_from_action_and_value(
        self,
        action: str,
        action_conf: float,
        value: int,
        value_conf: float,
        source: str,
    ) -> Dict[str, Any]:
        number = max(0, min(100, int(value)))
        conf = round(float((action_conf + value_conf) / 2), 4)

        if action == "increase":
            return {
                "mode": "delta",
                "delta": number,
                "confidence": conf,
                "debug": {"source": source, "action": action, "action_conf": round(float(action_conf), 4), "value": str(number), "value_conf": round(float(value_conf), 4)},
            }

        if action == "decrease":
            return {
                "mode": "delta",
                "delta": -number,
                "confidence": conf,
                "debug": {"source": source, "action": action, "action_conf": round(float(action_conf), 4), "value": str(number), "value_conf": round(float(value_conf), 4)},
            }

        return {
            "mode": "set",
            "percent": number,
            "confidence": conf,
            "debug": {"source": source, "action": action, "action_conf": round(float(action_conf), 4), "value": str(number), "value_conf": round(float(value_conf), 4)},
        }

    def _predict_label(self, model, text: str) -> Tuple[str, float]:
        label = model.predict([text])[0]
        confidence = 0.7
        if hasattr(model, "predict_proba"):
            try:
                proba = model.predict_proba([text])[0]
                confidence = float(max(proba))
            except Exception:
                confidence = 0.7
        return str(label), confidence

    def _parse_vague_label(self, label: str) -> Optional[Dict[str, Any]]:
        if not label or label == "UNKNOWN":
            return None
        if label.startswith("DELTA_PLUS_"):
            return {"mode": "delta", "delta": int(label.split("_")[-1])}
        if label.startswith("DELTA_MINUS_"):
            return {"mode": "delta", "delta": -int(label.split("_")[-1])}
        if label.startswith("SET_"):
            return {"mode": "set", "percent": max(0, min(100, int(label.split("_")[-1])))}
        return None

    def _debug(self, source, action, action_conf, value=None, value_conf=None, vague=None, vague_conf=None):
        data = {
            "source": source,
            "action": action,
            "action_conf": round(float(action_conf), 4),
        }
        if value is not None:
            data["value"] = value
            data["value_conf"] = round(float(value_conf), 4)
        if vague is not None:
            data["vague"] = vague
            data["vague_conf"] = round(float(vague_conf), 4)
        return data
