from __future__ import annotations

from typing import Any

from python_agent.api.result import ok, fail
from python_agent.ui.settings_store import UiSettings, UiSettingsStore
from python_agent.voice.settings import VoiceSettings


class SettingsApi:
    """
    Stable settings API.

    For now it reuses the existing UiSettingsStore to avoid changing the old UI.
    Later UiSettingsStore should be moved from ui/ to services/settings_service.py.
    """

    def __init__(self, store: UiSettingsStore | None = None) -> None:
        self.store = store or UiSettingsStore()

    def load(self) -> dict[str, Any]:
        try:
            return ok(self.store.load().to_dict())
        except Exception as error:
            return fail(error, code="SETTINGS_LOAD_ERROR")

    def save(self, settings: dict[str, Any]) -> dict[str, Any]:
        try:
            current = self.store.load()
            voice_payload = settings.get("voice", current.voice.to_dict())

            payload = UiSettings(
                text_hotkey_enabled=bool(
                    settings.get("text_hotkey_enabled", current.text_hotkey_enabled)
                ),
                text_hotkey_sequence=str(
                    settings.get("text_hotkey_sequence", current.text_hotkey_sequence)
                ),
                voice=VoiceSettings.from_dict(voice_payload),
            )
            self.store.save(payload)
            return ok(self.store.load().to_dict())
        except Exception as error:
            return fail(error, code="SETTINGS_SAVE_ERROR")
