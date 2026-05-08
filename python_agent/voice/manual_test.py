from __future__ import annotations

import json
import sys

from python_agent.services.settings_store import UiSettingsStore
from python_agent.voice.service import VoiceService


def main() -> int:
    settings = UiSettingsStore().load().voice
    result = VoiceService().test_microphone(settings, seconds=3.0)
    print(json.dumps({
        "transcript": result.transcript,
        "command_text": result.command_text,
        "ignored": result.ignored,
        "reason": result.reason,
        "meta": result.meta,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
