from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any


def normalize_app_id(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9_]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value


def ascii_slug(value: str) -> str:
    ascii_value = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    return normalize_app_id(ascii_value)


def suggest_app_id(display_name: str, launch_path: str | Path | None = None) -> str:
    candidates = [display_name]

    if launch_path is not None:
        path = Path(launch_path)
        candidates.extend([path.stem, path.parent.name])

    for candidate in candidates:
        slug = ascii_slug(str(candidate))
        if slug:
            return slug

    return "custom_app"


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