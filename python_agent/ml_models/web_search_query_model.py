from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QueryPattern:
    prefix: str
    suffix: str
    count: int = 1


@dataclass
class WebSearchQueryModel:
    patterns: list[QueryPattern]
    min_query_length: int = 2

    def predict(self, texts: list[str]) -> list[dict]:
        if not isinstance(texts, list):
            raise TypeError("WebSearchQueryModel.predict expects list[str]")

        return [self._predict_one(text) for text in texts]

    def _predict_one(self, text: str) -> dict:
        normalized = " ".join(str(text or "").lower().split())
        if not normalized:
            return {"missing": ["query"], "confidence": 0.0}

        for pattern in self.patterns:
            if pattern.prefix and not normalized.startswith(pattern.prefix):
                continue
            if pattern.suffix and not normalized.endswith(pattern.suffix):
                continue

            start = len(pattern.prefix)
            end = len(normalized) - len(pattern.suffix) if pattern.suffix else len(normalized)
            query = normalized[start:end].strip()
            if len(query) >= self.min_query_length:
                confidence = min(0.96, 0.55 + min(pattern.count, 40) / 100)
                return {"query": query, "confidence": round(confidence, 4)}

        return {"missing": ["query"], "confidence": 0.0}
