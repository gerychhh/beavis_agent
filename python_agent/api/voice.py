from __future__ import annotations

from typing import Any

from python_agent.api.result import ok, fail
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

    def __init__(self, service: VoiceService | None = None) -> None:
        self.service = service or VoiceService()

    def preload(self, settings: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            voice_settings = VoiceSettings.from_dict(settings)
            self.service.preload(voice_settings)
            return ok({"preloaded": True})
        except Exception as error:
            return fail(error, code="VOICE_PRELOAD_ERROR")

    def listen_once(
        self,
        settings: dict[str, Any] | None = None,
        mode: str = "hotkey",
        require_wake_word: bool = False,
    ) -> dict[str, Any]:
        try:
            voice_settings = VoiceSettings.from_dict(settings)
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
            voice_settings = VoiceSettings.from_dict(settings)
            result = self.service.test_microphone(
                voice_settings,
                seconds=seconds,
            )
            return ok(_voice_result_to_dict(result))
        except Exception as error:
            return fail(error, code="VOICE_TEST_ERROR")
