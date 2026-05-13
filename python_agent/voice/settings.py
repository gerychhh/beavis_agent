from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STT_MODEL_DIR = PROJECT_ROOT / "python_agent" / "models" / "stt"
DEFAULT_AGENT_NAMES = ("бивис", "beavis")
VOICE_MODES = {"off", "hotkey", "continuous"}
STT_PROFILES = {"auto", "turbo", "cpu", "accuracy", "custom"}
STT_MODEL_CHOICES = (
    "turbo",
    "large-v3-turbo",
    "small",
    "medium",
    "base",
    "tiny",
    "distil-large-v3",
    "large-v3",
)
STT_DEVICE_CHOICES = ("auto", "cpu", "cuda")
STT_COMPUTE_CHOICES = ("auto", "int8", "float16", "int8_float16", "float32")


@dataclass(frozen=True)
class VadSettings:
    sensitivity: float = 0.012
    start_grace_ms: int = 3000
    hotkey_silence_ms: int = 500
    continuous_silence_ms: int = 700
    max_utterance_ms: int = 7000
    block_ms: int = 50

    def to_dict(self) -> dict[str, Any]:
        return {
            "sensitivity": self.sensitivity,
            "start_grace_ms": self.start_grace_ms,
            "hotkey_silence_ms": self.hotkey_silence_ms,
            "continuous_silence_ms": self.continuous_silence_ms,
            "max_utterance_ms": self.max_utterance_ms,
            "block_ms": self.block_ms,
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "VadSettings":
        if not isinstance(payload, dict):
            return cls()
        return cls(
            sensitivity=_float(payload.get("sensitivity"), cls.sensitivity),
            start_grace_ms=_int(payload.get("start_grace_ms"), cls.start_grace_ms),
            hotkey_silence_ms=_int(payload.get("hotkey_silence_ms"), cls.hotkey_silence_ms),
            continuous_silence_ms=_int(payload.get("continuous_silence_ms"), cls.continuous_silence_ms),
            max_utterance_ms=_int(payload.get("max_utterance_ms"), cls.max_utterance_ms),
            block_ms=_int(payload.get("block_ms"), cls.block_ms),
        ).normalized()

    def normalized(self) -> "VadSettings":
        return VadSettings(
            sensitivity=max(0.001, min(0.20, float(self.sensitivity))),
            start_grace_ms=max(500, min(8000, int(self.start_grace_ms))),
            hotkey_silence_ms=max(150, min(2500, int(self.hotkey_silence_ms))),
            continuous_silence_ms=max(150, min(3000, int(self.continuous_silence_ms))),
            max_utterance_ms=max(1000, min(20000, int(self.max_utterance_ms))),
            block_ms=max(20, min(250, int(self.block_ms))),
        )


@dataclass(frozen=True)
class SttSettings:
    profile: str = "turbo"
    model_size: str = "turbo"
    device: str = "auto"
    compute_type: str = "auto"
    language: str = "ru"
    beam_size: int = 1
    vad_filter: bool = True
    condition_on_previous_text: bool = False
    temperature: float = 0.0
    transcribe_timeout_s: float = 30.0
    model_dir: str = str(DEFAULT_STT_MODEL_DIR)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "model_size": self.model_size,
            "device": self.device,
            "compute_type": self.compute_type,
            "language": self.language,
            "beam_size": self.beam_size,
            "vad_filter": self.vad_filter,
            "condition_on_previous_text": self.condition_on_previous_text,
            "temperature": self.temperature,
            "transcribe_timeout_s": self.transcribe_timeout_s,
            "model_dir": self.model_dir,
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "SttSettings":
        if not isinstance(payload, dict):
            return cls()
        return cls(
            profile=str(payload.get("profile") or cls.profile),
            model_size=str(payload.get("model_size") or cls.model_size),
            device=str(payload.get("device") or cls.device),
            compute_type=str(payload.get("compute_type") or cls.compute_type),
            language=str(payload.get("language") or cls.language),
            beam_size=_int(payload.get("beam_size"), cls.beam_size),
            vad_filter=bool(payload.get("vad_filter", cls.vad_filter)),
            condition_on_previous_text=bool(payload.get("condition_on_previous_text", cls.condition_on_previous_text)),
            temperature=_float(payload.get("temperature"), cls.temperature),
            transcribe_timeout_s=_float(payload.get("transcribe_timeout_s"), cls.transcribe_timeout_s),
            model_dir=str(payload.get("model_dir") or cls.model_dir),
        ).normalized()

    def normalized(self) -> "SttSettings":
        profile = self.profile if self.profile in STT_PROFILES else "auto"
        return SttSettings(
            profile=profile,
            model_size=self.model_size.strip() or "small",
            device=self.device.strip() or "auto",
            compute_type=self.compute_type.strip() or "auto",
            language=(self.language.strip() or "ru")[:12],
            beam_size=max(1, min(5, int(self.beam_size))),
            vad_filter=bool(self.vad_filter),
            condition_on_previous_text=bool(self.condition_on_previous_text),
            temperature=max(0.0, min(1.0, float(self.temperature))),
            transcribe_timeout_s=max(2.0, min(180.0, float(self.transcribe_timeout_s))),
            model_dir=str(Path(self.model_dir).expanduser()),
        )


@dataclass(frozen=True)
class VoiceSettings:
    mode: str = "hotkey"
    hotkey_enabled: bool = True
    hotkey_sequence: str = "Ctrl+Alt+V"
    microphone_device: str = ""
    agent_names: tuple[str, ...] = field(default_factory=lambda: DEFAULT_AGENT_NAMES)
    require_wake_word_for_continuous: bool = True
    preload_model_on_startup: bool = False
    stt: SttSettings = field(default_factory=SttSettings)
    vad: VadSettings = field(default_factory=VadSettings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "hotkey_enabled": self.hotkey_enabled,
            "hotkey_sequence": self.hotkey_sequence,
            "microphone_device": self.microphone_device,
            "agent_names": list(self.agent_names),
            "require_wake_word_for_continuous": self.require_wake_word_for_continuous,
            "preload_model_on_startup": self.preload_model_on_startup,
            "stt": self.stt.to_dict(),
            "vad": self.vad.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "VoiceSettings":
        if not isinstance(payload, dict):
            return cls()

        names = payload.get("agent_names")
        if isinstance(names, str):
            names = names.replace(",", "\n").splitlines()
        if not isinstance(names, list):
            names = list(DEFAULT_AGENT_NAMES)

        cleaned_names = tuple(dict.fromkeys(
            " ".join(str(item).lower().split())
            for item in names
            if " ".join(str(item).lower().split())
        ))

        return cls(
            mode=str(payload.get("mode") or cls.mode),
            hotkey_enabled=bool(payload.get("hotkey_enabled", cls.hotkey_enabled)),
            hotkey_sequence=str(payload.get("hotkey_sequence") or cls.hotkey_sequence),
            microphone_device=str(payload.get("microphone_device") or ""),
            agent_names=cleaned_names or DEFAULT_AGENT_NAMES,
            require_wake_word_for_continuous=bool(
                payload.get("require_wake_word_for_continuous", cls.require_wake_word_for_continuous)
            ),
            preload_model_on_startup=bool(payload.get("preload_model_on_startup", cls.preload_model_on_startup)),
            stt=SttSettings.from_dict(payload.get("stt")),
            vad=VadSettings.from_dict(payload.get("vad")),
        ).normalized()

    def normalized(self) -> "VoiceSettings":
        mode = self.mode if self.mode in VOICE_MODES else "hotkey"
        names = tuple(dict.fromkeys(
            " ".join(str(item).lower().split())
            for item in self.agent_names
            if " ".join(str(item).lower().split())
        )) or DEFAULT_AGENT_NAMES
        return VoiceSettings(
            mode=mode,
            hotkey_enabled=bool(self.hotkey_enabled),
            hotkey_sequence=self.hotkey_sequence or "Ctrl+Alt+V",
            microphone_device=self.microphone_device,
            agent_names=names,
            require_wake_word_for_continuous=bool(self.require_wake_word_for_continuous),
            preload_model_on_startup=bool(self.preload_model_on_startup),
            stt=self.stt.normalized(),
            vad=self.vad.normalized(),
        )


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
