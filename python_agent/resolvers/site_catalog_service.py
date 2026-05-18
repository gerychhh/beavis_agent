from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from python_agent.resolvers.app_catalog_utils import (
    normalize_app_id,
    normalize_speech_forms,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SITES_CATALOG_PATH = PROJECT_ROOT / "python_agent" / "data" / "sites" / "sites_catalog.json"

VALID_SOURCES = {"default", "user"}


def normalize_site_id(value: str) -> str:
    return normalize_app_id(value)


@dataclass(frozen=True)
class SiteRecord:
    site_id: str
    display_name: str
    source: str = "user"
    enabled: bool = True
    base_url: str = ""
    speech_forms: list[str] = field(default_factory=list)
    priority: int = 0

    @classmethod
    def from_dict(cls, item: dict[str, Any]) -> "SiteRecord":
        source = str(item.get("source") or "user").strip().lower()
        if source not in VALID_SOURCES:
            source = "user"

        return cls(
            site_id=normalize_site_id(str(item.get("site_id") or "")),
            display_name=str(item.get("display_name") or "").strip(),
            source=source,
            enabled=bool(item.get("enabled", True)),
            base_url=str(item.get("base_url") or "").strip(),
            speech_forms=normalize_speech_forms(item.get("speech_forms") or []),
            priority=int(item.get("priority") or 0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "site_id": self.site_id,
            "display_name": self.display_name,
            "source": self.source,
            "enabled": self.enabled,
            "base_url": self.base_url,
            "speech_forms": self.speech_forms,
            "priority": self.priority,
        }

    def validate(self) -> None:
        if not self.site_id:
            raise ValueError("site_id is required")
        if not self.display_name:
            raise ValueError("display_name is required")
        if self.source not in VALID_SOURCES:
            raise ValueError(f"invalid site source: {self.source}")
        if not _is_http_url(self.base_url):
            raise ValueError("base_url must be an http/https URL")


class SiteCatalogService:
    def __init__(self, catalog_path: str | Path | None = None) -> None:
        self.catalog_path = Path(catalog_path) if catalog_path else DEFAULT_SITES_CATALOG_PATH
        if not self.catalog_path.is_absolute():
            self.catalog_path = PROJECT_ROOT / self.catalog_path

    def load(self) -> list[SiteRecord]:
        if not self.catalog_path.exists():
            return []

        payload = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Sites catalog must be a JSON object: {self.catalog_path}")

        raw_sites = payload.get("sites", [])
        if not isinstance(raw_sites, list):
            raise ValueError(f"Sites catalog 'sites' must be a list: {self.catalog_path}")

        records: list[SiteRecord] = []
        for item in raw_sites:
            if not isinstance(item, dict):
                continue
            record = SiteRecord.from_dict(item)
            if record.site_id and record.display_name:
                records.append(record)
        return self._dedupe(records)

    def save(self, records: list[SiteRecord]) -> None:
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        clean_records = self._dedupe(records)
        clean_records.sort(key=lambda item: (item.source, item.site_id))
        payload = {
            "schema_version": 1,
            "sites": [record.to_dict() for record in clean_records],
        }
        self.catalog_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_all_sites(self) -> list[SiteRecord]:
        return self.load()

    def get_enabled_sites(self) -> list[SiteRecord]:
        return [record for record in self.load() if record.enabled]

    def get_site(self, site_id: str) -> SiteRecord | None:
        normalized = normalize_site_id(site_id)
        for record in self.load():
            if record.site_id == normalized:
                return record
        return None

    def add_site(self, record: SiteRecord, replace_existing: bool = False) -> SiteRecord:
        record = self._clean_record(record)
        record.validate()

        records = self.load()
        exists = any(item.site_id == record.site_id for item in records)
        if exists and not replace_existing:
            raise ValueError(f"site_id is already used: {record.site_id}")

        out = [item for item in records if item.site_id != record.site_id]
        out.append(record)
        self.save(out)
        return record

    def update_site(self, site_id: str, **changes: Any) -> SiteRecord:
        normalized = normalize_site_id(site_id)
        records = self.load()
        updated: SiteRecord | None = None
        out: list[SiteRecord] = []

        for record in records:
            if record.site_id != normalized:
                out.append(record)
                continue
            changes.pop("site_id", None)
            if "speech_forms" in changes:
                changes["speech_forms"] = normalize_speech_forms(changes["speech_forms"])
            if "source" in changes:
                changes["source"] = str(changes["source"]).strip().lower()
            updated = self._clean_record(replace(record, **changes))
            updated.validate()
            out.append(updated)

        if updated is None:
            raise ValueError(f"site not found: {normalized}")

        self.save(out)
        return updated

    def delete_site(self, site_id: str) -> SiteRecord:
        normalized = normalize_site_id(site_id)
        records = self.load()
        deleted: SiteRecord | None = None
        out: list[SiteRecord] = []

        for record in records:
            if record.site_id != normalized:
                out.append(record)
                continue
            deleted = record

        if deleted is None:
            raise ValueError(f"site not found: {normalized}")

        self.save(out)
        return deleted

    def _clean_record(self, record: SiteRecord) -> SiteRecord:
        speech_candidates = [
            record.display_name,
            record.site_id.replace("_", " "),
            *record.speech_forms,
        ]
        return SiteRecord(
            site_id=normalize_site_id(record.site_id),
            display_name=record.display_name.strip(),
            source=record.source.strip().lower() if record.source in VALID_SOURCES else "user",
            enabled=bool(record.enabled),
            base_url=record.base_url.strip(),
            speech_forms=normalize_speech_forms(speech_candidates),
            priority=int(record.priority or 0),
        )

    def _dedupe(self, records: list[SiteRecord]) -> list[SiteRecord]:
        by_id: dict[str, SiteRecord] = {}
        priority_by_source = {"default": 1, "user": 2}

        for record in records:
            cleaned = self._clean_record(record)
            if not cleaned.site_id:
                continue
            current = by_id.get(cleaned.site_id)
            if current is None:
                by_id[cleaned.site_id] = cleaned
                continue
            if priority_by_source.get(cleaned.source, 0) >= priority_by_source.get(current.source, 0):
                by_id[cleaned.site_id] = cleaned

        return list(by_id.values())


def _is_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
