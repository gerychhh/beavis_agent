import re
from typing import Any, Dict, List, Optional, Tuple


_UNIT_WORDS = {
    "ноль": 0,
    "нуль": 0,
    "один": 1,
    "одна": 1,
    "одну": 1,
    "два": 2,
    "две": 2,
    "три": 3,
    "четыре": 4,
    "пять": 5,
    "шесть": 6,
    "семь": 7,
    "сеть": 7,
    "восемь": 8,
    "девять": 9,
}
_TEEN_WORDS = {
    "десять": 10,
    "деисть": 10,
    "одиннадцать": 11,
    "двенадцать": 12,
    "тринадцать": 13,
    "четырнадцать": 14,
    "пятнадцать": 15,
    "шестнадцать": 16,
    "семнадцать": 17,
    "восемнадцать": 18,
    "девятнадцать": 19,
}
_TENS_WORDS = {
    "двадцать": 20,
    "дватцать": 20,
    "тридцать": 30,
    "сорок": 40,
    "пятьдесят": 50,
    "питдесят": 50,
    "полтинник": 50,
    "половина": 50,
    "половину": 50,
    "шестьдесят": 60,
    "семьдесят": 70,
    "семдесят": 70,
    "восемьдесят": 80,
    "девяносто": 90,
    "девяноста": 90,
    "сотня": 100,
    "сто": 100,
    "полная": 100,
    "полную": 100,
    "максимум": 100,
    "максималка": 100,
}
_NUMBER_WORDS = {**_UNIT_WORDS, **_TEEN_WORDS, **_TENS_WORDS}
_WORD_RE = re.compile(r"[a-zа-яё0-9]+", re.IGNORECASE)


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

        rule_vague = self._extract_rule_vague(text, action, action_conf)
        if rule_vague is not None:
            return rule_vague

        # 1) Value model: exact value or NO_VALUE.
        value, value_conf = self._predict_label(self.value_model, text)
        rule_value = self._extract_rule_value(text)
        if rule_value is not None and value_conf < 0.2:
            return self._build_from_action_and_value(
                action=action,
                action_conf=action_conf,
                value=rule_value,
                value_conf=1.0,
                source="rule_value",
            )

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

        if rule_value is not None:
            return self._build_from_action_and_value(
                action=action,
                action_conf=action_conf,
                value=rule_value,
                value_conf=1.0,
                source="rule_value",
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

    def _extract_rule_value(self, text: str) -> Optional[int]:
        normalized = text.lower().replace("ё", "е")
        tokens = _WORD_RE.findall(normalized)

        index = 0
        while index < len(tokens):
            token = tokens[index]
            value = self._parse_number_token(token)
            if value is None:
                index += 1
                continue

            if value in {20, 30, 40, 50, 60, 70, 80, 90} and index + 1 < len(tokens):
                next_value = self._parse_number_token(tokens[index + 1])
                if next_value is not None:
                    if 0 <= next_value <= 9:
                        return max(0, min(100, int(value + next_value)))

            return max(0, min(100, int(value)))
        return None

    def _parse_number_token(self, token: str) -> Optional[int]:
        if token.isdigit():
            return int(token)
        return _NUMBER_WORDS.get(token)

    def _extract_rule_vague(
        self,
        text: str,
        action: str,
        action_conf: float,
    ) -> Optional[Dict[str, Any]]:
        normalized = text.lower().replace("ё", "е")
        if "еле слышно" in normalized or "едва слышно" in normalized:
            return {
                "mode": "delta",
                "delta": 15,
                "confidence": round(float(max(action_conf, 0.9)), 4),
                "debug": {
                    "source": "rule_vague",
                    "action": action,
                    "action_conf": round(float(action_conf), 4),
                    "vague": "barely_audible",
                },
            }
        return None

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
