from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from python_agent.resolvers.app_catalog_utils import (
    normalize_app_id,
    normalize_speech_forms,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_APPS_CATALOG_PATH = PROJECT_ROOT / "python_agent" / "data" / "apps" / "apps_catalog.json"

VALID_SOURCES = {"builtin", "default", "user"}


@dataclass(frozen=True)
class AppRecord:
    app_id: str
    display_name: str
    source: str = "user"
    enabled: bool = True
    launch_type: str = "exe"
    launch_target: str = ""
    target_path: str = ""
    working_directory: str = ""
    speech_forms: list[str] = field(default_factory=list)
    priority: int = 0

    @classmethod
    def from_dict(cls, item: dict[str, Any]) -> "AppRecord":
        app_id = normalize_app_id(str(item.get("app_id") or ""))
        display_name = str(item.get("display_name") or "").strip()
        source = str(item.get("source") or "user").strip().lower()

        if source not in VALID_SOURCES:
            source = "user"

        launch_target = str(item.get("launch_target") or "").strip()
        target_path = str(item.get("target_path") or launch_target).strip()

        return cls(
            app_id=app_id,
            display_name=display_name,
            source=source,
            enabled=bool(item.get("enabled", True)),
            launch_type=str(item.get("launch_type") or "exe").strip() or "exe",
            launch_target=launch_target,
            target_path=target_path,
            working_directory=str(item.get("working_directory") or "").strip(),
            speech_forms=normalize_speech_forms(item.get("speech_forms") or []),
            priority=int(item.get("priority") or 0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "app_id": self.app_id,
            "display_name": self.display_name,
            "source": self.source,
            "enabled": self.enabled,
            "launch_type": self.launch_type,
            "launch_target": self.launch_target,
            "target_path": self.target_path or self.launch_target,
            "working_directory": self.working_directory,
            "speech_forms": self.speech_forms,
            "priority": self.priority,
        }

    def validate(self) -> None:
        if not self.app_id:
            raise ValueError("app_id is required")

        if not self.display_name:
            raise ValueError("display_name is required")

        if self.source not in VALID_SOURCES:
            raise ValueError(f"invalid app source: {self.source}")

        if not self.launch_target and self.source != "builtin":
            raise ValueError("launch_target is required")


class AppCatalogService:
    def __init__(self, catalog_path: str | Path | None = None) -> None:
        self.catalog_path = Path(catalog_path) if catalog_path else DEFAULT_APPS_CATALOG_PATH

        if not self.catalog_path.is_absolute():
            self.catalog_path = PROJECT_ROOT / self.catalog_path

    def load(self) -> list[AppRecord]:
        if not self.catalog_path.exists():
            return []

        payload = json.loads(self.catalog_path.read_text(encoding="utf-8"))

        if not isinstance(payload, dict):
            raise ValueError(f"Apps catalog must be a JSON object: {self.catalog_path}")

        raw_apps = payload.get("apps", [])

        if not isinstance(raw_apps, list):
            raise ValueError(f"Apps catalog 'apps' must be a list: {self.catalog_path}")

        records: list[AppRecord] = []

        for item in raw_apps:
            if not isinstance(item, dict):
                continue

            record = AppRecord.from_dict(item)

            if not record.app_id or not record.display_name:
                continue

            records.append(record)

        return self._dedupe(records)

    def save(self, records: list[AppRecord]) -> None:
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)

        clean_records = self._dedupe(records)
        clean_records.sort(key=lambda item: (item.source, item.app_id))

        payload = {
            "schema_version": 1,
            "apps": [record.to_dict() for record in clean_records],
        }

        self.catalog_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_all_apps(self) -> list[AppRecord]:
        return self.load()

    def get_enabled_apps(self) -> list[AppRecord]:
        return [record for record in self.load() if record.enabled]

    def get_app(self, app_id: str) -> AppRecord | None:
        normalized = normalize_app_id(app_id)

        for record in self.load():
            if record.app_id == normalized:
                return record

        return None

    def add_app(self, record: AppRecord, replace_existing: bool = False) -> AppRecord:
        record = self._clean_record(record)
        record.validate()

        records = self.load()
        exists = any(item.app_id == record.app_id for item in records)

        if exists and not replace_existing:
            raise ValueError(f"app_id is already used: {record.app_id}")

        out = [item for item in records if item.app_id != record.app_id]
        out.append(record)
        self.save(out)
        return record

    def update_app(self, app_id: str, **changes: Any) -> AppRecord:
        normalized = normalize_app_id(app_id)
        records = self.load()

        updated: AppRecord | None = None
        out: list[AppRecord] = []

        for record in records:
            if record.app_id != normalized:
                out.append(record)
                continue

            if "app_id" in changes:
                changes.pop("app_id")

            if "speech_forms" in changes:
                changes["speech_forms"] = normalize_speech_forms(changes["speech_forms"])

            if "source" in changes:
                changes["source"] = str(changes["source"]).strip().lower()

            updated = self._clean_record(replace(record, **changes))
            updated.validate()
            out.append(updated)

        if updated is None:
            raise ValueError(f"app not found: {normalized}")

        self.save(out)
        return updated

    def enable_app(self, app_id: str) -> AppRecord:
        return self.update_app(app_id, enabled=True)

    def disable_app(self, app_id: str) -> AppRecord:
        return self.update_app(app_id, enabled=False)

    def delete_user_app(self, app_id: str) -> AppRecord:
        normalized = normalize_app_id(app_id)
        records = self.load()

        deleted: AppRecord | None = None
        out: list[AppRecord] = []

        for record in records:
            if record.app_id != normalized:
                out.append(record)
                continue

            if record.source != "user":
                raise ValueError(
                    f"Only user apps can be physically deleted. Disable instead: {normalized}"
                )

            deleted = record

        if deleted is None:
            raise ValueError(f"user app not found: {normalized}")

        self.save(out)
        return deleted

    def _clean_record(self, record: AppRecord) -> AppRecord:
        return AppRecord(
            app_id=normalize_app_id(record.app_id),
            display_name=record.display_name.strip(),
            source=record.source.strip().lower() if record.source in VALID_SOURCES else "user",
            enabled=bool(record.enabled),
            launch_type=record.launch_type.strip() or "exe",
            launch_target=record.launch_target.strip(),
            target_path=(record.target_path or record.launch_target).strip(),
            working_directory=record.working_directory.strip(),
            speech_forms=normalize_speech_forms(
                [
                    record.display_name,
                    Path(record.launch_target).stem if record.launch_target else "",
                    *record.speech_forms,
                ]
            ),
            priority=int(record.priority or 0),
        )

    def _dedupe(self, records: list[AppRecord]) -> list[AppRecord]:
        by_id: dict[str, AppRecord] = {}

        priority_by_source = {
            "builtin": 1,
            "default": 2,
            "user": 3,
        }

        for record in records:
            cleaned = self._clean_record(record)

            if not cleaned.app_id:
                continue

            current = by_id.get(cleaned.app_id)

            if current is None:
                by_id[cleaned.app_id] = cleaned
                continue

            current_priority = priority_by_source.get(current.source, 0)
            new_priority = priority_by_source.get(cleaned.source, 0)

            if new_priority >= current_priority:
                by_id[cleaned.app_id] = cleaned

        return list(by_id.values())