from __future__ import annotations

import re
import unicodedata
from pathlib import Path, PureWindowsPath
from typing import Any

_CYR_TO_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "",
    "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}

_RESERVED_APP_IDS = {"", "app", "custom_app"}


def transliterate(value: str) -> str:
    return "".join(_CYR_TO_LAT.get(ch.lower(), ch) for ch in str(value))


def normalize_app_id(value: str) -> str:
    value = str(value).strip().lower()
    value = transliterate(value)
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-z0-9_]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value


def ascii_slug(value: str) -> str:
    return normalize_app_id(value)


def _path_candidates(value: str | Path | None) -> list[str]:
    if value is None:
        return []

    text = str(value).strip()
    if not text:
        return []

    candidates: list[str] = []

    win_path = PureWindowsPath(text)
    candidates.extend([win_path.stem, win_path.name, win_path.parent.name])

    posix_path = Path(text)
    candidates.extend([posix_path.stem, posix_path.name, posix_path.parent.name])

    # URI-like launch targets: steam://rungameid/629520 -> keep last segment too.
    if "://" in text:
        tail = text.rstrip("/").rsplit("/", 1)[-1]
        candidates.append(tail)

    if "!" in text:
        candidates.append(text.rsplit("!", 1)[-1])

    return [candidate for candidate in candidates if candidate]


def suggest_app_id(display_name: str, launch_path: str | Path | None = None) -> str:
    candidates = [display_name, *_path_candidates(launch_path)]

    for candidate in candidates:
        slug = normalize_app_id(str(candidate))
        if slug and slug not in _RESERVED_APP_IDS:
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
        cleaned = " ".join(str(item).strip().lower().split())
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            out.append(cleaned)

    return out
