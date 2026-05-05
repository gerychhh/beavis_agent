from __future__ import annotations

from pathlib import Path
from typing import Any

from python_agent.nlu.normalizer import Normalizer
from python_agent.resolvers.app_catalog_service import AppCatalogService, AppRecord
from python_agent.resolvers.app_catalog_utils import normalize_app_id


class AppSearch:
    """
    Search only inside the unified app catalog.

    Architecture rule:
    - source of truth: python_agent/data/apps/apps_catalog.json
    - searchable apps: AppCatalogService.get_enabled_apps()
    - disabled apps are invisible here
    """

    def __init__(
        self,
        normalizer: Normalizer | None = None,
        catalog_service: AppCatalogService | None = None,
    ) -> None:
        self.normalizer = normalizer or Normalizer()
        self.catalog_service = catalog_service or AppCatalogService()
        self._records: list[dict[str, Any]] | None = None
        self._app_ids: set[str] | None = None
        self._candidate_to_app_id: dict[str, str] | None = None
        self._text_candidates: list[tuple[str, str, int]] | None = None

    def reload(self) -> None:
        self._records = None
        self._app_ids = None
        self._candidate_to_app_id = None
        self._text_candidates = None

    def has_app(self, app_id: str) -> bool:
        normalized = normalize_app_id(app_id)
        return bool(normalized and normalized in self.active_app_ids())

    def resolve_app_id(self, query: str) -> str | None:
        normalized_app_id = normalize_app_id(query)

        if normalized_app_id in self.active_app_ids():
            return normalized_app_id

        query_key = self._key(query)
        if not query_key:
            return None

        return self._candidate_map().get(query_key)

    def find_app_ids_in_text(self, text: str, limit: int = 4) -> list[str]:
        text_key = self._key(text)
        if not text_key:
            return []

        padded_text = f" {text_key} "
        compact_text = text_key.replace(" ", "")
        found: list[str] = []

        for candidate, app_id, _priority in self._text_candidate_list():
            padded_candidate = f" {candidate} "
            compact_candidate = candidate.replace(" ", "")

            matched = padded_candidate in padded_text
            if not matched and len(compact_candidate) >= 4:
                matched = compact_candidate in compact_text

            if matched and app_id not in found:
                found.append(app_id)

            if len(found) >= limit:
                break

        return found

    def active_app_ids(self) -> set[str]:
        if self._app_ids is None:
            self._app_ids = {
                normalize_app_id(str(record.get("app_id") or ""))
                for record in self.records()
                if record.get("app_id")
            }
            self._app_ids.discard("")
        return self._app_ids

    def records(self) -> list[dict[str, Any]]:
        if self._records is not None:
            return self._records

        self._records = [
            self._record_to_dict(app)
            for app in self.catalog_service.get_enabled_apps()
        ]
        return self._records

    def _record_to_dict(self, app: AppRecord) -> dict[str, Any]:
        return {
            "app_id": app.app_id,
            "display_name": app.display_name,
            "display_names": app.speech_forms,
            "source": app.source,
            "enabled": app.enabled,
            "launch_type": app.launch_type,
            "launch_target": app.launch_target,
            "target_path": app.target_path or app.launch_target,
            "working_directory": app.working_directory,
            "priority": app.priority,
        }

    def _candidate_map(self) -> dict[str, str]:
        if self._candidate_to_app_id is not None:
            return self._candidate_to_app_id

        candidates: dict[str, str] = {}

        for record in self.records():
            app_id = normalize_app_id(str(record.get("app_id") or ""))
            if not app_id:
                continue

            for value in self._candidate_values(record):
                key = self._key(value)
                if key and key not in candidates:
                    candidates[key] = app_id

        self._candidate_to_app_id = candidates
        return candidates

    def _text_candidate_list(self) -> list[tuple[str, str, int]]:
        if self._text_candidates is not None:
            return self._text_candidates

        rows: list[tuple[str, str, int]] = []

        for record in self.records():
            app_id = normalize_app_id(str(record.get("app_id") or ""))
            if not app_id:
                continue

            priority = int(record.get("priority") or 0)

            for value in self._candidate_values(record):
                key = self._key(value)
                compact = key.replace(" ", "")
                if len(compact) < 3:
                    continue

                rows.append((key, app_id, priority))

        rows = list(dict.fromkeys(rows))
        rows.sort(key=lambda item: (-len(item[0]), -item[2], item[1]))
        self._text_candidates = rows
        return rows

    def _candidate_values(self, record: dict[str, Any]) -> list[str]:
        values: list[str] = [
            str(record.get("app_id") or ""),
            str(record.get("app_id") or "").replace("_", " "),
            str(record.get("display_name") or ""),
            Path(str(record.get("target_path") or "")).stem,
            Path(str(record.get("launch_target") or "")).stem,
        ]

        display_names = record.get("display_names")
        if isinstance(display_names, list):
            values.extend(str(item) for item in display_names)

        out: list[str] = []
        seen: set[str] = set()
        for value in values:
            key = str(value).strip()
            if key and key not in seen:
                seen.add(key)
                out.append(key)
        return out

    def _key(self, value: str) -> str:
        return self.normalizer.normalize(str(value))
