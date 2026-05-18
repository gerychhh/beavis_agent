from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote_plus

from python_agent.core.schemas import ArgsPrediction
from python_agent.nlu.argument_extractors.base import ArgumentExtractor
from python_agent.nlu.argument_extractors.web_search_model import WebSearchModelExtractor


SEARCH_PREFIXES = (
    "найди в интернете",
    "поищи в интернете",
    "найди в гугле",
    "поищи в гугле",
    "найди через гугл",
    "поищи через гугл",
    "search for",
    "look up",
    "загугли",
    "погугли",
    "найди",
    "поищи",
    "google",
    "search",
)
QUESTION_PREFIXES = (
    "что такое",
    "кто такой",
    "кто такая",
    "как работает",
    "как установить",
    "как настроить",
    "почему",
    "где находится",
    "мне нужно узнать",
    "узнай",
    "расскажи про",
    "информация про",
)
TRAILING_PROVIDER_RE = re.compile(
    r"\s+(?:в\s+)?(?:google|гугле|гугл|интернете|web|браузере)$",
    flags=re.IGNORECASE,
)
WAKE_WORDS = (
    "beavis",
    "bavis",
    "бивис",
    "бывис",
)
EDGE_NOISE_WORDS = (
    "эй",
    "слушай",
    "брух",
    "ну",
    "пожалуйста",
    "плиз",
)


class WebSearchExtractor(ArgumentExtractor):
    def __init__(
        self,
        provider: str = "google",
        model_extractor: WebSearchModelExtractor | None = None,
        model_path: str | Path | None = None,
    ) -> None:
        self.provider = provider
        self.model_extractor = model_extractor or WebSearchModelExtractor(model_path=model_path)

    def extract(self, text: str) -> ArgsPrediction:
        model_prediction = self.model_extractor.extract(text)
        query = str(model_prediction.args.get("query") or "").strip()
        source = model_prediction.source
        confidence = model_prediction.confidence

        if not query:
            normalized = self._normalize_text(text)
            query = self._extract_query_by_rules(normalized)
            source = "web_search_rules"
            confidence = 0.92

        query = self._clean_query(query)
        if not query:
            return ArgsPrediction(args={}, confidence=0.0, missing=["query"], source="web_search_missing_query")

        return ArgsPrediction(
            args={
                "action": "search",
                "provider": self.provider,
                "query": query,
                "url": self._build_url(query),
            },
            confidence=confidence,
            missing=[],
            source=source,
        )

    def _extract_query_by_rules(self, normalized: str) -> str:
        for prefix in sorted((*SEARCH_PREFIXES, *QUESTION_PREFIXES), key=len, reverse=True):
            if normalized == prefix:
                return ""
            if normalized.startswith(prefix + " "):
                return normalized[len(prefix):].strip()

        return ""

    def _build_url(self, query: str) -> str:
        return f"https://www.google.com/search?q={quote_plus(query)}"

    def _clean_query(self, query: str) -> str:
        cleaned = str(query or "").strip(" \t\r\n\"'")
        cleaned = TRAILING_PROVIDER_RE.sub("", cleaned).strip()
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _normalize_text(self, text: str) -> str:
        normalized = str(text or "").lower().replace("ё", "е")
        normalized = re.sub(r"[,.!?;:()\[\]{}\"']", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return self._strip_leading_noise(normalized)

    def _strip_leading_noise(self, text: str) -> str:
        changed = True
        out = text
        while changed:
            changed = False
            for word in (*EDGE_NOISE_WORDS, *WAKE_WORDS):
                if out == word:
                    return ""
                if out.startswith(word + " "):
                    out = out[len(word):].strip()
                    changed = True
                    break
        return out
