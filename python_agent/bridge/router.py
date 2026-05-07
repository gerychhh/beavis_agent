from __future__ import annotations

from typing import Any

from python_agent.api.facade import BeavisApi
from python_agent.api.result import fail


class BridgeRouter:
    def __init__(self, api: BeavisApi | None = None) -> None:
        self.api = api or BeavisApi()

    def dispatch(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}

        try:
            if method == "system.health":
                return self.api.health()

            if method == "commands.run":
                return self.api.commands.run(**params)
            if method == "commands.build_tool_call":
                return self.api.commands.build_tool_call(**params)
            if method == "commands.reload":
                return self.api.commands.reload()

            if method == "apps.list_windows_apps":
                return self.api.apps.list_windows_apps()
            if method == "apps.list_user_apps":
                return self.api.apps.list_user_apps()
            if method == "apps.add":
                return self.api.apps.add(**params)
            if method == "apps.update_speech_forms":
                return self.api.apps.update_speech_forms(**params)
            if method == "apps.delete":
                return self.api.apps.delete(**params)
            if method == "apps.apply_changes":
                return self.api.apps.apply_changes(**params)
            if method == "apps.retrain_start":
                return self.api.apps.retrain_start()
            if method == "apps.retrain_status":
                return self.api.apps.retrain_status()

            if method == "voice.preload":
                return self.api.voice.preload(**params)
            if method == "voice.listen_once":
                return self.api.voice.listen_once(**params)
            if method == "voice.test_microphone":
                return self.api.voice.test_microphone(**params)
            if method == "voice.list_microphones":
                return self.api.voice.list_microphones()

            if method == "settings.load":
                return self.api.settings.load()
            if method == "settings.save":
                # settings.save receives the whole settings object as params.
                return self.api.settings.save(params)

            if method == "history.list":
                return self.api.history.list(**params)
            if method == "history.mark":
                return self.api.history.mark(**params)

            return fail(f"Unknown method: {method}", code="UNKNOWN_METHOD")
        except TypeError as error:
            return fail(error, code="BAD_PARAMS")
        except Exception as error:
            return fail(error, code="BRIDGE_ROUTER_ERROR")
