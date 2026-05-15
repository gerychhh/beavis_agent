from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from python_agent.services.settings_store import UiSettings, UiSettingsStore
from python_agent.voice.service import build_voice_command_result
from python_agent.voice.settings import VadSettings, VoiceSettings
from python_agent.voice.stt import TranscriptionResult, resolve_runtime
from python_agent.voice.vad import EnergyVad
from python_agent.voice.wake_word import strip_wake_word


def check_settings_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "ui_settings.json"
        store = UiSettingsStore(path)
        settings = store.load()
        assert settings.text_hotkey_sequence == "Ctrl+Alt+Space"
        assert settings.voice.hotkey_sequence == "Ctrl+Alt+V"
        assert settings.voice.vad.start_grace_ms == 3000

        changed = UiSettings(
            text_hotkey_enabled=False,
            text_hotkey_sequence="Ctrl+Shift+Space",
            voice=VoiceSettings(mode="continuous", agent_names=("бивис", "beavis", "би"), hotkey_sequence="Ctrl+Alt+V"),
        )
        store.save(changed)
        loaded = store.load()
        assert loaded.text_hotkey_enabled is False
        assert loaded.text_hotkey_sequence == "Ctrl+Shift+Space"
        assert loaded.voice.mode == "continuous"
        assert "би" in loaded.voice.agent_names

        path.write_text("{broken", encoding="utf-8")
        assert store.load().voice.mode == "hotkey"


def check_wake_word() -> None:
    matched = strip_wake_word("бивис открой хром", ("бивис", "beavis"))
    assert matched.matched
    assert matched.command_text == "открой хром"

    missing = strip_wake_word("открой хром", ("бивис", "beavis"))
    assert not missing.matched
    assert missing.command_text == "открой хром"


def check_vad() -> None:
    vad = EnergyVad(VoiceSettings().vad)
    assert not vad.decide(np.zeros(1600, dtype=np.float32)).is_speech
    assert vad.decide(np.ones(1600, dtype=np.float32) * 0.1).is_speech
    assert VadSettings(start_grace_ms=100).normalized().start_grace_ms == 500
    assert VadSettings(start_grace_ms=9000).normalized().start_grace_ms == 8000


def check_voice_command_result() -> None:
    transcription = TranscriptionResult(
        text="бивис открой хром",
        confidence=0.91,
        language="ru",
        duration=1.2,
        model_size="small",
        device="cpu",
        compute_type="int8",
    )
    result = build_voice_command_result(
        transcription,
        VoiceSettings(),
        audio_duration_ms=1300,
        peak_rms=0.05,
        require_wake_word=True,
    )
    assert not result.ignored
    assert result.command_text == "открой хром"
    assert result.meta["wake_word_matched"] is True

    ignored = build_voice_command_result(
        TranscriptionResult("открой хром", 0.8, "ru", 1.0, "small", "cpu", "int8"),
        VoiceSettings(),
        audio_duration_ms=1000,
        peak_rms=0.05,
        require_wake_word=True,
    )
    assert ignored.ignored
    assert ignored.reason == "wake_word_missing"


def check_tiny_runtime() -> None:
    runtime = resolve_runtime(VoiceSettings().stt)
    assert runtime.model_size in {"turbo", "small"}

    tiny = VoiceSettings().stt.__class__(
        profile="custom",
        model_size="tiny",
        device="auto",
        compute_type="auto",
        transcribe_timeout_s=5,
    )
    tiny_runtime = resolve_runtime(tiny)
    assert tiny_runtime.model_size == "tiny"
    assert tiny_runtime.device == "cpu"
    assert tiny_runtime.compute_type == "int8"
    assert tiny.normalized().transcribe_timeout_s == 5


def main() -> int:
    checks = {
        "settings_roundtrip": check_settings_roundtrip,
        "wake_word": check_wake_word,
        "vad": check_vad,
        "voice_command_result": check_voice_command_result,
        "tiny_runtime": check_tiny_runtime,
    }
    failed: list[str] = []
    for name, check in checks.items():
        try:
            check()
        except Exception:
            failed.append(name)
            raise

    print(json.dumps({"checks": list(checks), "failed": failed}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
