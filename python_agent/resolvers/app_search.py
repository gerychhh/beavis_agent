from __future__ import annotations

from pathlib import Path
from typing import Any

from python_agent.nlu.normalizer import Normalizer
from python_agent.resolvers.app_catalog_service import AppCatalogService, AppRecord
from python_agent.resolvers.app_catalog_utils import normalize_app_id


class AppSearch:
    """Resolve application names using the unified app catalog only.

    Source of truth:
        python_agent/data/apps/apps_catalog.json

    Policy:
        enabled=True  -> available for resolving/searching
        enabled=False -> completely ignored by AppSearch
    """

    def __init__(
        self,
        normalizer: Normalizer | None = None,
        catalog_service: AppCatalogService | None = None,
    ) -> None:
        self.normalizer = normalizer or Normalizer()
        self.catalog_service = catalog_service or AppCatalogService()
        self.reload()

    def reload(self) -> None:
        self._records: list[dict[str, Any]] | None = None
        self._app_ids: set[str] | None = None
        self._candidate_to_app_id: dict[str, str] | None = None
        self._text_candidates: list[tuple[str, str, int]] | None = None

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

        direct = self._candidate_map().get(query_key)
        if direct:
            return direct

        compact_query = self._compact_key(query_key)
        if compact_query:
            return self._candidate_map().get(compact_query)

        return None

    def find_app_ids_in_text(self, text: str, limit: int = 4) -> list[str]:
        text_key = self._key(text)
        if not text_key:
            return []

        text_compact = self._compact_key(text_key)
        found: list[str] = []

        for candidate, app_id, _priority in self._text_candidate_list():
            if app_id in found:
                continue

            candidate_compact = self._compact_key(candidate)

            if self._contains_phrase(text_key, candidate) or (
                candidate_compact and candidate_compact in text_compact
            ):
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
            self._record_to_dict(record)
            for record in self.catalog_service.get_enabled_apps()
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
                if not key:
                    continue

                candidates.setdefault(key, app_id)

                compact = self._compact_key(key)
                if compact:
                    candidates.setdefault(compact, app_id)

        self._candidate_to_app_id = candidates
        return candidates

    def _text_candidate_list(self) -> list[tuple[str, str, int]]:
        if self._text_candidates is not None:
            return self._text_candidates

        rows: list[tuple[str, str, int]] = []
        seen: set[tuple[str, str]] = set()

        for record in self.records():
            app_id = normalize_app_id(str(record.get("app_id") or ""))
            if not app_id:
                continue

            priority = int(record.get("priority") or 0)

            for value in self._candidate_values(record):
                key = self._key(value)
                compact = self._compact_key(key)

                # Very short aliases like "ya", "vk", "tg" are too ambiguous for
                # scanning full text unless user explicitly keeps them as full app
                # names and the model returns them directly via resolve_app_id().
                if len(compact) < 3:
                    continue

                pair = (key, app_id)
                if key and pair not in seen:
                    rows.append((key, app_id, priority))
                    seen.add(pair)

        # Prefer more specific names first:
        # "яндекс музыка" must beat "яндекс".
        rows.sort(key=lambda item: (-len(self._compact_key(item[0])), -item[2], item[1]))

        self._text_candidates = rows
        return rows

    def _candidate_values(self, record: dict[str, Any]) -> list[str]:
        app_id = str(record.get("app_id") or "")
        launch_target = str(record.get("launch_target") or "")
        target_path = str(record.get("target_path") or "")

        values: list[str] = [
            app_id,
            app_id.replace("_", " "),
            str(record.get("display_name") or ""),
            Path(target_path).stem,
            Path(launch_target).stem,
        ]

        display_names = record.get("display_names")
        if isinstance(display_names, list):
            values.extend(str(item) for item in display_names)

        out: list[str] = []
        seen: set[str] = set()

        for value in values:
            normalized = " ".join(str(value).strip().split())
            if normalized and normalized not in seen:
                seen.add(normalized)
                out.append(normalized)

        return out

    def _key(self, value: str) -> str:
        return self.normalizer.normalize(str(value))

    def _compact_key(self, value: str) -> str:
        return self._key(value).replace(" ", "")

    def _contains_phrase(self, text_key: str, candidate_key: str) -> bool:
        if not candidate_key:
            return False
        return f" {candidate_key} " in f" {text_key} "
