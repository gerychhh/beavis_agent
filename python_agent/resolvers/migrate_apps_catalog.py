from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from python_agent.resolvers.app_catalog_service import AppCatalogService, AppRecord
from python_agent.resolvers.app_catalog_utils import normalize_app_id, normalize_speech_forms
from python_agent.resolvers.user_app_catalog import load_user_apps
from python_agent.resolvers.app_catalog_overrides import load_app_catalog_overrides
from python_agent.training.dataset_sources import dict_from_source, load_training_source


DEFAULT_INDEX_PATH = PROJECT_ROOT / "python_agent" / "data" / "cache" / "apps_index.json"


def records_from_builtin() -> list[AppRecord]:
    source = load_training_source("open_app.json")
    app_catalog = dict_from_source(source, "app_catalog")

    records: list[AppRecord] = []

    for app_id, entry in app_catalog.items():
        if not isinstance(entry, dict):
            continue

        normalized_app_id = normalize_app_id(app_id)
        surface_forms = normalize_speech_forms(entry.get("surface_forms") or [])
        display_name = surface_forms[0] if surface_forms else normalized_app_id

        records.append(
            AppRecord(
                app_id=normalized_app_id,
                display_name=display_name,
                source="builtin",
                enabled=True,
                launch_type="builtin",
                launch_target="",
                target_path="",
                working_directory="",
                speech_forms=normalize_speech_forms(
                    [
                        *surface_forms,
                        *(entry.get("typos") or []),
                        *(entry.get("semantic") or []),
                    ]
                ),
                priority=100,
            )
        )

    return records


def records_from_user_apps() -> list[AppRecord]:
    records: list[AppRecord] = []

    for item in load_user_apps():
        records.append(
            AppRecord(
                app_id=item.app_id,
                display_name=item.display_name,
                source="user",
                enabled=True,
                launch_type=item.launch_type,
                launch_target=item.launch_target,
                target_path=item.target_path,
                working_directory=item.working_directory,
                speech_forms=item.speech_forms,
                priority=300,
            )
        )

    return records


def records_from_apps_index(index_path: Path = DEFAULT_INDEX_PATH) -> list[AppRecord]:
    if not index_path.exists():
        return []

    payload = json.loads(index_path.read_text(encoding="utf-8"))

    if not isinstance(payload, dict):
        return []

    raw_records = payload.get("records", [])

    if not isinstance(raw_records, list):
        return []

    records: list[AppRecord] = []

    for item in raw_records:
        if not isinstance(item, dict):
            continue

        app_id = normalize_app_id(str(item.get("app_id") or ""))
        display_name = str(item.get("display_name") or app_id).strip()
        launch_target = str(item.get("launch_target") or "").strip()
        target_path = str(item.get("target_path") or launch_target).strip()

        if not app_id or not display_name:
            continue

        display_names = item.get("display_names")
        forms = display_names if isinstance(display_names, list) else []

        records.append(
            AppRecord(
                app_id=app_id,
                display_name=display_name,
                source="default",
                enabled=True,
                launch_type=str(item.get("launch_type") or "exe").strip() or "exe",
                launch_target=launch_target,
                target_path=target_path,
                working_directory=str(item.get("working_directory") or "").strip(),
                speech_forms=normalize_speech_forms(
                    [
                        display_name,
                        Path(target_path).stem if target_path else "",
                        Path(launch_target).stem if launch_target else "",
                        *forms,
                    ]
                ),
                priority=int(item.get("priority") or 200),
            )
        )

    return records


def apply_legacy_overrides(records: list[AppRecord]) -> list[AppRecord]:
    overrides = load_app_catalog_overrides()
    out: list[AppRecord] = []

    for record in records:
        override = overrides.get(record.app_id)

        if override is None:
            out.append(record)
            continue

        speech_forms = record.speech_forms

        if override.speech_forms:
            speech_forms = normalize_speech_forms(
                [
                    record.display_name,
                    *record.speech_forms,
                    *override.speech_forms,
                ]
            )

        out.append(
            AppRecord(
                app_id=record.app_id,
                display_name=record.display_name,
                source=record.source,
                enabled=not override.disabled,
                launch_type=record.launch_type,
                launch_target=record.launch_target,
                target_path=record.target_path,
                working_directory=record.working_directory,
                speech_forms=speech_forms,
                priority=record.priority,
            )
        )

    return out


def migrate() -> None:
    service = AppCatalogService()

    records = [
        *records_from_builtin(),
        *records_from_apps_index(),
        *records_from_user_apps(),
    ]

    records = apply_legacy_overrides(records)
    service.save(records)

    print(f"migrated apps: {len(service.get_all_apps())}")
    print(f"catalog: {service.catalog_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    migrate()


if __name__ == "__main__":
    main()