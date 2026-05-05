from __future__ import annotations

from python_agent.api.apps import AppsApi
from python_agent.api.commands import CommandsApi
from python_agent.api.history import HistoryApi
from python_agent.api.settings import SettingsApi
from python_agent.api.voice import VoiceApi


class BeavisApi:
    """
    Single stable entry point for any UI.

    Old PySide UI can stay untouched.
    New UI should talk to this facade through bridge/stdio_server.py.
    """

    def __init__(self) -> None:
        self._commands: CommandsApi | None = None
        self._apps: AppsApi | None = None
        self._voice: VoiceApi | None = None
        self._history: HistoryApi | None = None
        self._settings: SettingsApi | None = None

    @property
    def commands(self) -> CommandsApi:
        if self._commands is None:
            self._commands = CommandsApi()
        return self._commands

    @property
    def apps(self) -> AppsApi:
        if self._apps is None:
            self._apps = AppsApi()
        return self._apps

    @property
    def voice(self) -> VoiceApi:
        if self._voice is None:
            self._voice = VoiceApi()
        return self._voice

    @property
    def history(self) -> HistoryApi:
        if self._history is None:
            self._history = HistoryApi()
        return self._history

    @property
    def settings(self) -> SettingsApi:
        if self._settings is None:
            self._settings = SettingsApi()
        return self._settings

    def health(self) -> dict:
        return {
            "ok": True,
            "data": {
                "service": "beavis_api",
                "status": "ready",
                "methods": [
                    "system.health",
                    "commands.run",
                    "commands.build_tool_call",
                    "commands.reload",
                    "apps.list_windows_apps",
                    "apps.list_user_apps",
                    "apps.add",
                    "apps.update_speech_forms",
                    "apps.delete",
                    "apps.apply_changes",
                    "voice.preload",
                    "voice.listen_once",
                    "voice.test_microphone",
                    "settings.load",
                    "settings.save",
                    "history.list",
                    "history.mark",
                ],
            },
            "error": None,
            "code": None,
            "meta": {},
        }
