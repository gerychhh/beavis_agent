from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from python_agent.resolvers.user_app_catalog import normalize_app_id, normalize_speech_forms


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_APP_OVERRIDES_PATH = PROJECT_ROOT / "python_agent" / "data" / "user_apps" / "catalog_overrides.json"


@dataclass(frozen=True)
class AppCatalogOverride:
    app_id: str
    speech_forms: list[str] = field(default_factory=list)
    disabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "app_id": self.app_id,
            "speech_forms": self.speech_forms,
            "disabled": self.disabled,
        }


def load_app_catalog_overrides(path: str | Path | None = None) -> dict[str, AppCatalogOverride]:
    overrides_path = Path(path) if path else DEFAULT_APP_OVERRIDES_PATH
    if not overrides_path.exists():
        return {}

    payload = json.loads(overrides_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"App catalog overrides must be a JSON object: {overrides_path}")

    raw_items = payload.get("overrides", {})
    if isinstance(raw_items, list):
        iterable = raw_items
    elif isinstance(raw_items, dict):
        iterable = [
            {"app_id": app_id, **item}
            for app_id, item in raw_items.items()
            if isinstance(item, dict)
        ]
    else:
        raise ValueError(f"App catalog overrides 'overrides' must be an object or list: {overrides_path}")

    out: dict[str, AppCatalogOverride] = {}
    for item in iterable:
        if not isinstance(item, dict):
            continue
        app_id = normalize_app_id(str(item.get("app_id") or ""))
        if not app_id:
            continue
        out[app_id] = AppCatalogOverride(
            app_id=app_id,
            speech_forms=normalize_speech_forms(item.get("speech_forms") or []),
            disabled=bool(item.get("disabled", False)),
        )

    return out


def save_app_catalog_overrides(
    overrides: dict[str, AppCatalogOverride],
    path: str | Path | None = None,
) -> None:
    overrides_path = Path(path) if path else DEFAULT_APP_OVERRIDES_PATH
    overrides_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned = {
        app_id: override
        for app_id, override in sorted(overrides.items())
        if override.disabled or override.speech_forms
    }
    payload = {
        "schema_version": 1,
        "overrides": {
            app_id: override.to_dict()
            for app_id, override in cleaned.items()
        },
    }
    overrides_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def update_app_catalog_speech_forms(
    app_id: str,
    speech_forms: list[str],
    path: str | Path | None = None,
) -> AppCatalogOverride:
    normalized_app_id = normalize_app_id(app_id)
    if not normalized_app_id:
        raise ValueError("app_id is required")

    overrides = load_app_catalog_overrides(path)
    current = overrides.get(normalized_app_id, AppCatalogOverride(app_id=normalized_app_id))
    updated = AppCatalogOverride(
        app_id=normalized_app_id,
        speech_forms=normalize_speech_forms(speech_forms),
        disabled=current.disabled,
    )
    overrides[normalized_app_id] = updated
    save_app_catalog_overrides(overrides, path)
    return updated


def disable_app_catalog_entry(
    app_id: str,
    path: str | Path | None = None,
) -> AppCatalogOverride:
    normalized_app_id = normalize_app_id(app_id)
    if not normalized_app_id:
        raise ValueError("app_id is required")

    overrides = load_app_catalog_overrides(path)
    current = overrides.get(normalized_app_id, AppCatalogOverride(app_id=normalized_app_id))
    updated = AppCatalogOverride(
        app_id=normalized_app_id,
        speech_forms=current.speech_forms,
        disabled=True,
    )
    overrides[normalized_app_id] = updated
    save_app_catalog_overrides(overrides, path)
    return updated


def active_disabled_app_ids(path: str | Path | None = None) -> set[str]:
    return {
        app_id
        for app_id, override in load_app_catalog_overrides(path).items()
        if override.disabled
    }
