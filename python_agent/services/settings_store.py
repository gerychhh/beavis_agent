from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from python_agent.services.hotkey_utils import normalize_hotkey_sequence
from python_agent.voice.settings import VoiceSettings


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SETTINGS_PATH = PROJECT_ROOT / "python_agent" / "data" / "settings" / "ui_settings.json"


@dataclass(frozen=True)
class UiSettings:
    text_hotkey_enabled: bool = True
    text_hotkey_sequence: str = "Ctrl+Alt+Space"
    voice: VoiceSettings = field(default_factory=VoiceSettings)

    @property
    def hotkey_enabled(self) -> bool:
        return self.text_hotkey_enabled

    @property
    def hotkey_sequence(self) -> str:
        return self.text_hotkey_sequence

    def to_dict(self) -> dict[str, Any]:
        return {
            "text_hotkey_enabled": self.text_hotkey_enabled,
            "text_hotkey_sequence": self.text_hotkey_sequence,
            "voice": self.voice.to_dict(),
        }


class UiSettingsStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_SETTINGS_PATH

    def load(self) -> UiSettings:
        if not self.path.exists():
            return UiSettings()

        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return UiSettings()

        if not isinstance(payload, dict):
            return UiSettings()

        default = UiSettings()
        enabled = bool(payload.get("text_hotkey_enabled", payload.get("hotkey_enabled", default.text_hotkey_enabled)))
        sequence = str(payload.get("text_hotkey_sequence", payload.get("hotkey_sequence", default.text_hotkey_sequence)))
        voice = VoiceSettings.from_dict(payload.get("voice"))

        try:
            sequence = normalize_hotkey_sequence(sequence)
        except ValueError:
            sequence = default.text_hotkey_sequence

        try:
            voice_sequence = normalize_hotkey_sequence(voice.hotkey_sequence)
            voice = VoiceSettings(
                mode=voice.mode,
                hotkey_enabled=voice.hotkey_enabled,
                hotkey_sequence=voice_sequence,
                microphone_device=voice.microphone_device,
                agent_names=voice.agent_names,
                require_wake_word_for_continuous=voice.require_wake_word_for_continuous,
                preload_model_on_startup=voice.preload_model_on_startup,
                stt=voice.stt,
                vad=voice.vad,
            )
        except ValueError:
            voice = VoiceSettings(
                mode=voice.mode,
                hotkey_enabled=voice.hotkey_enabled,
                hotkey_sequence=default.voice.hotkey_sequence,
                microphone_device=voice.microphone_device,
                agent_names=voice.agent_names,
                require_wake_word_for_continuous=voice.require_wake_word_for_continuous,
                preload_model_on_startup=voice.preload_model_on_startup,
                stt=voice.stt,
                vad=voice.vad,
            )

        return UiSettings(
            text_hotkey_enabled=enabled,
            text_hotkey_sequence=sequence,
            voice=voice.normalized(),
        )

    def save(self, settings: UiSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        voice_hotkey = normalize_hotkey_sequence(settings.voice.hotkey_sequence)
        voice = VoiceSettings(
            mode=settings.voice.mode,
            hotkey_enabled=settings.voice.hotkey_enabled,
            hotkey_sequence=voice_hotkey,
            microphone_device=settings.voice.microphone_device,
            agent_names=settings.voice.agent_names,
            require_wake_word_for_continuous=settings.voice.require_wake_word_for_continuous,
            preload_model_on_startup=settings.voice.preload_model_on_startup,
            stt=settings.voice.stt,
            vad=settings.voice.vad,
        ).normalized()
        normalized = UiSettings(
            text_hotkey_enabled=settings.text_hotkey_enabled,
            text_hotkey_sequence=normalize_hotkey_sequence(settings.text_hotkey_sequence),
            voice=voice,
        )
        self.path.write_text(
            json.dumps(normalized.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
