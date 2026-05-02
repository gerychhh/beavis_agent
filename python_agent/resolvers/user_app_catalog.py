from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_USER_APPS_PATH = PROJECT_ROOT / "python_agent" / "data" / "user_apps" / "apps.json"


@dataclass(frozen=True)
class UserAppRecord:
    app_id: str
    display_name: str
    launch_target: str
    launch_type: str = "exe"
    target_path: str = ""
    working_directory: str = ""
    speech_forms: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "app_id": self.app_id,
            "display_name": self.display_name,
            "launch_type": self.launch_type,
            "launch_target": self.launch_target,
            "target_path": self.target_path or self.launch_target,
            "working_directory": self.working_directory,
            "speech_forms": self.speech_forms,
        }


def load_user_apps(path: str | Path | None = None) -> list[UserAppRecord]:
    catalog_path = Path(path) if path else DEFAULT_USER_APPS_PATH
    if not catalog_path.exists():
        return []

    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"User apps catalog must be a JSON object: {catalog_path}")

    apps = payload.get("apps", [])
    if not isinstance(apps, list):
        raise ValueError(f"User apps catalog 'apps' must be a list: {catalog_path}")

    records: list[UserAppRecord] = []
    for item in apps:
        if not isinstance(item, dict):
            continue

        app_id = normalize_app_id(str(item.get("app_id") or ""))
        display_name = str(item.get("display_name") or "").strip()
        launch_target = str(item.get("launch_target") or "").strip()
        if not app_id or not display_name or not launch_target:
            continue

        speech_forms = normalize_speech_forms(item.get("speech_forms") or [])
        target_path = str(item.get("target_path") or launch_target).strip()
        working_directory = str(item.get("working_directory") or "").strip()

        records.append(UserAppRecord(
            app_id=app_id,
            display_name=display_name,
            launch_type=str(item.get("launch_type") or "exe").strip() or "exe",
            launch_target=launch_target,
            target_path=target_path,
            working_directory=working_directory,
            speech_forms=speech_forms,
        ))

    return records


def save_user_apps(records: list[UserAppRecord], path: str | Path | None = None) -> None:
    catalog_path = Path(path) if path else DEFAULT_USER_APPS_PATH
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "apps": [record.to_dict() for record in records],
    }
    catalog_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_user_app_record(
    *,
    path: str | Path,
    display_name: str,
    app_id: str | None = None,
    speech_forms: list[str] | None = None,
) -> UserAppRecord:
    launch_path = Path(path).expanduser()
    display_name = display_name.strip()
    if not display_name:
        raise ValueError("Display name is required")

    normalized_app_id = normalize_app_id(app_id or suggest_app_id(display_name, launch_path))
    if not normalized_app_id:
        raise ValueError("app_id is required")

    forms = normalize_speech_forms([
        display_name,
        launch_path.stem,
        *(speech_forms or []),
    ])

    return UserAppRecord(
        app_id=normalized_app_id,
        display_name=display_name,
        launch_type="exe",
        launch_target=str(launch_path),
        target_path=str(launch_path),
        working_directory=str(launch_path.parent),
        speech_forms=forms,
    )


def build_windows_user_app_record(
    *,
    windows_app_id: str,
    display_name: str,
    launch_type: str = "apps_folder",
    launch_target: str | None = None,
    app_id: str | None = None,
    speech_forms: list[str] | None = None,
) -> UserAppRecord:
    windows_app_id = windows_app_id.strip()
    display_name = display_name.strip()
    launch_type = launch_type.strip() or "apps_folder"
    if not windows_app_id:
        raise ValueError("Windows app id is required")
    if not display_name:
        raise ValueError("Display name is required")

    normalized_app_id = normalize_app_id(app_id or suggest_app_id(display_name, windows_app_id))
    if not normalized_app_id:
        raise ValueError("app_id is required")

    target = (launch_target or "").strip()
    if not target:
        target = f"shell:AppsFolder\\{windows_app_id}" if launch_type == "apps_folder" else windows_app_id

    forms = normalize_speech_forms([
        display_name,
        windows_app_id,
        *(speech_forms or []),
    ])

    return UserAppRecord(
        app_id=normalized_app_id,
        display_name=display_name,
        launch_type=launch_type,
        launch_target=target,
        target_path=windows_app_id,
        working_directory="",
        speech_forms=forms,
    )


def add_user_app_record(
    record: UserAppRecord,
    path: str | Path | None = None,
    existing_app_ids: set[str] | None = None,
) -> list[UserAppRecord]:
    records = load_user_apps(path)
    known_ids = {item.app_id for item in records}
    if existing_app_ids:
        known_ids.update(existing_app_ids)

    if record.app_id in known_ids:
        raise ValueError(f"app_id is already used: {record.app_id}")

    records.append(record)
    records.sort(key=lambda item: item.app_id)
    save_user_apps(records, path)
    return records


def update_user_app_speech_forms(
    app_id: str,
    speech_forms: list[str],
    path: str | Path | None = None,
) -> UserAppRecord:
    normalized_app_id = normalize_app_id(app_id)
    if not normalized_app_id:
        raise ValueError("app_id is required")

    records = load_user_apps(path)
    updated: UserAppRecord | None = None
    out: list[UserAppRecord] = []
    for record in records:
        if record.app_id != normalized_app_id:
            out.append(record)
            continue

        updated = UserAppRecord(
            app_id=record.app_id,
            display_name=record.display_name,
            launch_type=record.launch_type,
            launch_target=record.launch_target,
            target_path=record.target_path,
            working_directory=record.working_directory,
            speech_forms=normalize_speech_forms(speech_forms),
        )
        out.append(updated)

    if updated is None:
        raise ValueError(f"user app not found: {normalized_app_id}")

    out.sort(key=lambda item: item.app_id)
    save_user_apps(out, path)
    return updated


def delete_user_app_record(
    app_id: str,
    path: str | Path | None = None,
) -> UserAppRecord:
    normalized_app_id = normalize_app_id(app_id)
    if not normalized_app_id:
        raise ValueError("app_id is required")

    records = load_user_apps(path)
    deleted: UserAppRecord | None = None
    out: list[UserAppRecord] = []
    for record in records:
        if record.app_id == normalized_app_id:
            deleted = record
            continue
        out.append(record)

    if deleted is None:
        raise ValueError(f"user app not found: {normalized_app_id}")

    out.sort(key=lambda item: item.app_id)
    save_user_apps(out, path)
    return deleted


def normalize_app_id(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9_]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value


def suggest_app_id(display_name: str, launch_path: str | Path | None = None) -> str:
    candidates = [display_name]
    if launch_path is not None:
        path = Path(launch_path)
        candidates.extend([path.stem, path.parent.name])

    for candidate in candidates:
        slug = ascii_slug(candidate)
        if slug:
            return slug

    return "custom_app"


def ascii_slug(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return normalize_app_id(ascii_value)


def normalize_speech_forms(value: Any) -> list[str]:
    raw: list[str] = []
    if isinstance(value, str):
        raw = [value]
    elif isinstance(value, list):
        raw = [str(item) for item in value]

    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        cleaned = " ".join(item.strip().lower().split())
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            out.append(cleaned)

    return out
