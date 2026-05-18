from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from python_agent.core.schemas import ArgsPrediction
from python_agent.nlu.argument_extractors.base import ArgumentExtractor
from python_agent.nlu.argument_extractors.web_open_model import WebOpenModelExtractor
from python_agent.resolvers.site_catalog_service import SiteCatalogService, SiteRecord


OPEN_PREFIXES = (
    "открой сайт",
    "открой ссылку",
    "открой",
    "перейди на",
    "зайди на",
    "go to",
    "open",
)
SEARCH_INTENT_RE = re.compile(
    r"^(?:найди|поищи|загугли|погугли|search(?:\s+for)?|google)\b",
    flags=re.IGNORECASE,
)

SITE_PREPOSITIONS = (
    "на",
    "в",
    "во",
    "через",
    "on",
    "in",
)

EDGE_NOISE_WORDS = (
    "эй",
    "слушай",
    "брух",
    "ну",
    "давай",
    "пожалуйста",
    "плиз",
    "быстро",
    "сейчас",
)

WAKE_WORDS = (
    "beavis",
    "bavis",
    "бивис",
    "бывис",
)

BARE_URL_RE = re.compile(
    r"^(?:"
    r"(?:www\.)?[a-z0-9][a-z0-9-]*(?:\.[a-z0-9][a-z0-9-]*)+"
    r"|localhost"
    r"|(?:\d{1,3}\.){3}\d{1,3}"
    r")(?::\d{1,5})?(?:/[^\s]*)?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SiteMatch:
    site: SiteRecord
    form: str
    start: int
    end: int
    explicit: bool


class WebOpenExtractor(ArgumentExtractor):
    def __init__(
        self,
        sites_catalog_path: str | Path | None = None,
        site_service: SiteCatalogService | None = None,
        model_extractor: WebOpenModelExtractor | None = None,
    ) -> None:
        self.site_service = site_service or SiteCatalogService(sites_catalog_path)
        self.model_extractor = model_extractor or WebOpenModelExtractor()

    def extract(self, text: str) -> ArgsPrediction:
        url_body = self._strip_command_prefix(self._normalize_url_text(text))
        direct_url = self._coerce_url(url_body)
        if direct_url:
            return ArgsPrediction(
                args={
                    "action": "open",
                    "url": direct_url,
                },
                confidence=0.96,
                missing=[],
                source="web_open_direct_url",
            )

        normalized = self._normalize_command_text(text)
        if SEARCH_INTENT_RE.match(normalized):
            return ArgsPrediction(
                args={},
                confidence=0.0,
                missing=["url"],
                source="web_open_search_rejected",
            )

        body = self._strip_command_prefix(normalized)
        sites = self._enabled_sites()

        match = self._find_site(body, sites)
        if match is None:
            model_prediction = self.model_extractor.extract(text)
            site_id = model_prediction.args.get("site_id")
            site = self.site_service.get_site(str(site_id)) if site_id else None
            if site is not None and site.enabled:
                return ArgsPrediction(
                    args={
                        "action": "open",
                        "site_id": site.site_id,
                        "url": site.base_url,
                    },
                    confidence=model_prediction.confidence,
                    missing=[],
                    source=model_prediction.source,
                )

            return ArgsPrediction(args={}, confidence=0.0, missing=["url"], source="web_open_rules_missing")

        site = match.site

        return ArgsPrediction(
            args={
                "action": "open",
                "site_id": site.site_id,
                "url": site.base_url,
            },
            confidence=0.92,
            missing=[],
            source="web_open_rules",
        )

    def _enabled_sites(self) -> list[SiteRecord]:
        return sorted(
            self.site_service.get_enabled_sites(),
            key=lambda site: (site.priority, len(site.display_name)),
            reverse=True,
        )

    def _strip_command_prefix(self, text: str) -> str:
        lowered = text.lower()
        for prefix in sorted(OPEN_PREFIXES, key=len, reverse=True):
            if lowered == prefix:
                return ""
            if lowered.startswith(prefix + " "):
                return text[len(prefix):].strip()

        return text.strip()

    def _find_site(
        self,
        body: str,
        sites: list[SiteRecord],
    ) -> SiteMatch | None:
        candidates: list[SiteMatch] = []

        for site in sites:
            forms = self._site_forms(site)
            for form in forms:
                escaped = re.escape(form)
                for prep in SITE_PREPOSITIONS:
                    pattern = rf"(?<!\w){re.escape(prep)}\s+{escaped}(?!\w)"
                    found = re.search(pattern, body, flags=re.IGNORECASE)
                    if found:
                        candidates.append(SiteMatch(site, form, found.start(), found.end(), True))

                direct_pattern = rf"(?<!\w){escaped}(?!\w)"
                found = re.search(direct_pattern, body, flags=re.IGNORECASE)
                if not found:
                    continue
                direct = SiteMatch(site, form, found.start(), found.end(), False)
                if body.strip() == form:
                    candidates.append(direct)

        if not candidates:
            return None

        return max(
            candidates,
            key=lambda item: (
                1 if item.explicit else 0,
                item.site.priority,
                len(item.form),
            ),
        )

    def _site_forms(self, site: SiteRecord) -> list[str]:
        raw_forms = [site.display_name, site.site_id.replace("_", " "), *site.speech_forms]
        forms: list[str] = []
        seen: set[str] = set()
        for raw in raw_forms:
            form = self._normalize_command_text(str(raw), strip_wake=False)
            if form and form not in seen:
                seen.add(form)
                forms.append(form)
        return sorted(forms, key=len, reverse=True)

    def _coerce_url(self, value: str) -> str | None:
        candidate = value.strip()
        candidate = re.sub(r"^(сайт|ссылку|url|урл)\s+", "", candidate, flags=re.IGNORECASE).strip()
        if not candidate or " " in candidate:
            return None

        if candidate.lower().startswith(("http://", "https://")):
            return candidate if self._is_http_url(candidate) else None

        if BARE_URL_RE.match(candidate):
            return f"https://{candidate}"

        return None

    def _is_http_url(self, value: str) -> bool:
        try:
            parsed = urlparse(value)
        except Exception:
            return False
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def _normalize_command_text(self, text: str, strip_wake: bool = True) -> str:
        normalized = str(text or "").lower().replace("ё", "е")
        normalized = re.sub(r"[,.!?;:()\[\]{}\"']", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        if strip_wake:
            normalized = self._strip_leading_noise(normalized)
        return normalized

    def _normalize_url_text(self, text: str) -> str:
        normalized = str(text or "").replace("Ё", "Е").replace("ё", "е")
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return self._strip_leading_noise(normalized)

    def _strip_leading_noise(self, text: str) -> str:
        changed = True
        out = text
        while changed:
            changed = False
            lowered = out.lower()
            for word in (*EDGE_NOISE_WORDS, *WAKE_WORDS):
                if lowered == word:
                    return ""
                if lowered.startswith(word + " "):
                    out = out[len(word):].strip()
                    changed = True
                    break
        return out
