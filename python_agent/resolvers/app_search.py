from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from python_agent.nlu.normalizer import Normalizer
from python_agent.resolvers import app_indexer
from python_agent.resolvers.app_catalog_overrides import (
    DEFAULT_APP_OVERRIDES_PATH,
    active_disabled_app_ids,
)
from python_agent.resolvers.user_app_catalog import normalize_app_id


class AppSearch:
    def __init__(
        self,
        index_path: str | Path | None = None,
        overrides_path: str | Path | None = DEFAULT_APP_OVERRIDES_PATH,
        normalizer: Normalizer | None = None,
    ) -> None:
        self.index_path = Path(index_path) if index_path else app_indexer.DEFAULT_OUTPUT_PATH
        self.overrides_path = Path(overrides_path) if overrides_path else DEFAULT_APP_OVERRIDES_PATH
        self.normalizer = normalizer or Normalizer()
        self._records: list[dict[str, Any]] | None = None
        self._app_ids: set[str] | None = None
        self._candidate_to_app_id: dict[str, str] | None = None
        self._text_candidates: list[tuple[str, str, int]] | None = None
        self._disabled_candidates: list[tuple[str, str]] | None = None

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

        found: list[str] = []
        for candidate, app_id, _priority in self._text_candidate_list():
            if candidate in text_key and app_id not in found:
                found.append(app_id)
                if len(found) >= limit:
                    break
        return found

    def find_disabled_app_ids_in_text(self, text: str, limit: int = 4) -> list[str]:
        text_key = self._key(text)
        if not text_key:
            return []

        found: list[str] = []
        for candidate, app_id in self._disabled_candidate_list():
            if candidate in text_key and app_id not in found:
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

        if not self.index_path.exists():
            self._records = []
            return self._records

        payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        raw_records = payload.get("records", []) if isinstance(payload, dict) else []
        disabled = active_disabled_app_ids(self.overrides_path)
        records: list[dict[str, Any]] = []
        for record in raw_records:
            if not isinstance(record, dict):
                continue
            app_id = normalize_app_id(str(record.get("app_id") or ""))
            if not app_id:
                continue
            if app_id in disabled and record.get("source") != "user":
                continue
            records.append(record)

        self._records = records
        return records

    def _candidate_map(self) -> dict[str, str]:
        if self._candidate_to_app_id is not None:
            return self._candidate_to_app_id

        candidates: dict[str, str] = {}
        for record in self.records():
            app_id = normalize_app_id(str(record.get("app_id") or ""))
            if not app_id:
                continue

            values: list[str] = [
                app_id,
                str(record.get("display_name") or ""),
                Path(str(record.get("target_path") or "")).stem,
                Path(str(record.get("launch_target") or "")).stem,
            ]
            display_names = record.get("display_names")
            if isinstance(display_names, list):
                values.extend(str(item) for item in display_names)

            for value in values:
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

            values: list[str] = [
                app_id,
                str(record.get("display_name") or ""),
                Path(str(record.get("target_path") or "")).stem,
                Path(str(record.get("launch_target") or "")).stem,
            ]
            display_names = record.get("display_names")
            if isinstance(display_names, list):
                values.extend(str(item) for item in display_names)

            priority = int(record.get("priority") or 0)
            for value in values:
                key = self._key(value)
                compact = key.replace(" ", "")
                if len(compact) < 3:
                    continue
                rows.append((key, app_id, priority))

        rows = list(dict.fromkeys(rows))
        rows.sort(key=lambda item: (-len(item[0]), -item[2], item[1]))
        self._text_candidates = rows
        return rows

    def _disabled_candidate_list(self) -> list[tuple[str, str]]:
        if self._disabled_candidates is not None:
            return self._disabled_candidates

        disabled = active_disabled_app_ids(self.overrides_path)
        rows: list[tuple[str, str]] = []
        if disabled:
            try:
                from python_agent.training.generate_open_app_dataset import APP_CATALOG
            except Exception:
                APP_CATALOG = {}

            for app_id in sorted(disabled):
                entry = APP_CATALOG.get(app_id, {}) if isinstance(APP_CATALOG, dict) else {}
                values = [app_id]
                if isinstance(entry, dict):
                    values.extend(entry.get("surface_forms", []))
                    values.extend(entry.get("typos", []))
                    values.extend(entry.get("semantic", []))

                for value in values:
                    key = self._key(str(value))
                    compact = key.replace(" ", "")
                    if key != self._key(app_id) and " " not in key and len(compact) < 8:
                        continue
                    if key:
                        rows.append((key, app_id))

        rows = list(dict.fromkeys(rows))
        rows.sort(key=lambda item: (-len(item[0]), item[1]))
        self._disabled_candidates = rows
        return rows

    def _key(self, value: str) -> str:
        return self.normalizer.normalize(str(value))
