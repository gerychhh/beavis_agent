from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRAINING_SOURCES_DIR = PROJECT_ROOT / "python_agent" / "data" / "training_sources"


def load_training_source(name: str) -> dict[str, Any]:
    source_path = TRAINING_SOURCES_DIR / name
    if not source_path.exists():
        raise FileNotFoundError(f"Training source is missing: {source_path}")

    payload = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Training source must be a JSON object: {source_path}")

    return payload


def list_from_source(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"Training source key must be a list: {key}")
    return list(value)


def dict_from_source(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"Training source key must be an object: {key}")
    return dict(value)


def int_key_dict_from_source(payload: dict[str, Any], key: str) -> dict[int, Any]:
    return {int(item_key): item_value for item_key, item_value in dict_from_source(payload, key).items()}
