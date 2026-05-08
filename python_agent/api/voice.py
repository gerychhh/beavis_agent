from __future__ import annotations

from typing import Any

from python_agent.api.result import ok, fail
from python_agent.voice import audio as audio_capture
from python_agent.services.settings_store import UiSettingsStore
from python_agent.voice.service import VoiceService, VoiceCommandResult
from python_agent.voice.settings import VoiceSettings


def _voice_result_to_dict(result: VoiceCommandResult) -> dict[str, Any]:
    return {
        "command_text": result.command_text,
        "transcript": result.transcript,
        "ignored": result.ignored,
        "reason": result.reason,
        "meta": dict(result.meta),
    }


class VoiceApi:
    """
    Stable API for one-shot voice operations.

    Continuous listening should be controlled by the UI shell/adapter because it
    needs lifecycle and event handling.
    """

    def __init__(
        self,
        service: VoiceService | None = None,
        settings_store: UiSettingsStore | None = None,
    ) -> None:
        self.service = service or VoiceService()
        self.settings_store = settings_store or UiSettingsStore()

    def _voice_settings(self, settings: dict[str, Any] | None = None) -> VoiceSettings:
        if settings is not None:
            return VoiceSettings.from_dict(settings)
        return self.settings_store.load().voice

    def preload(self, settings: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            voice_settings = self._voice_settings(settings)
            self.service.preload(voice_settings)
            return ok({"preloaded": True})
        except Exception as error:
            return fail(error, code="VOICE_PRELOAD_ERROR")

    def list_microphones(self) -> dict[str, Any]:
        try:
            devices = audio_capture.list_input_devices()
            return ok([
                {
                    "value": str(item.get("id") or ""),
                    "label": str(item.get("name") or item.get("id") or "Default input"),
                    "channels": item.get("channels"),
                    "default_samplerate": item.get("default_samplerate"),
                }
                for item in devices
            ])
        except Exception as error:
            return fail(error, code="VOICE_MICROPHONES_ERROR")

    def listen_once(
        self,
        settings: dict[str, Any] | None = None,
        mode: str = "hotkey",
        require_wake_word: bool = False,
    ) -> dict[str, Any]:
        try:
            voice_settings = self._voice_settings(settings)
            result = self.service.listen_once(
                voice_settings,
                mode=mode,
                require_wake_word=require_wake_word,
            )
            return ok(_voice_result_to_dict(result))
        except Exception as error:
            return fail(error, code="VOICE_LISTEN_ERROR")

    def test_microphone(
        self,
        settings: dict[str, Any] | None = None,
        seconds: float = 3.0,
    ) -> dict[str, Any]:
        try:
            voice_settings = self._voice_settings(settings)
            result = self.service.test_microphone(
                voice_settings,
                seconds=seconds,
            )
            return ok(_voice_result_to_dict(result))
        except Exception as error:
            return fail(error, code="VOICE_TEST_ERROR")
