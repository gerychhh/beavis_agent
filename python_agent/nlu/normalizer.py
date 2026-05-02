from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "normalizer.json"


class Normalizer:
    def __init__(self, config_path: str | Path | None = None) -> None:
        self.config_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        config = self._load_config(self.config_path)
        self.remove_words = [str(word).lower() for word in config.get("remove_words", [])]
        self.replacements = {
            str(source).lower(): str(target).lower()
            for source, target in config.get("replacements", {}).items()
        }

    def normalize(self, text: str) -> str:
        normalized = text.lower().replace("ё", "е")
        normalized = normalized.replace("%", " процентов ")
        normalized = self._replace_punctuation_with_spaces(normalized)
        normalized = self._apply_replacements(normalized)
        normalized = self._remove_noise_words(normalized)
        normalized = self._squash_spaces(normalized)
        return normalized

    def _load_config(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"remove_words": [], "replacements": {}}

        with path.open("r", encoding="utf-8") as file:
            config = json.load(file)

        if not isinstance(config, dict):
            raise ValueError(f"Normalizer config must be a JSON object: {path}")

        return config

    def _apply_replacements(self, text: str) -> str:
        normalized = text
        for source, target in sorted(self.replacements.items(), key=lambda item: len(item[0]), reverse=True):
            normalized = self._replace_term(normalized, source, target)
        return normalized

    def _remove_noise_words(self, text: str) -> str:
        normalized = text
        for word in sorted(self.remove_words, key=len, reverse=True):
            normalized = self._replace_term(normalized, word, " ")
        return normalized

    def _replace_term(self, text: str, source: str, target: str) -> str:
        escaped = re.escape(source)
        pattern = rf"(?<!\w){escaped}(?!\w)"
        return re.sub(pattern, target, text, flags=re.IGNORECASE)

    def _replace_punctuation_with_spaces(self, text: str) -> str:
        return re.sub(r"[,.!?;:()\[\]{}\"']", " ", text)

    def _squash_spaces(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()


def normalize(text: str, config_path: str | Path | None = None) -> str:
    return Normalizer(config_path=config_path).normalize(text)
