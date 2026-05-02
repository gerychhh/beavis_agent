from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable

import numpy as np

from python_agent.voice.settings import VadSettings, VoiceSettings
from python_agent.voice.vad import EnergyVad


SAMPLE_RATE = 16000


@dataclass(frozen=True)
class AudioCaptureResult:
    audio: np.ndarray
    duration_ms: int
    peak_rms: float
    speech_detected: bool


def list_input_devices() -> list[dict[str, object]]:
    try:
        import sounddevice as sd
    except ImportError:
        return []

    devices = sd.query_devices()
    out: list[dict[str, object]] = []
    for index, device in enumerate(devices):
        if int(device.get("max_input_channels", 0)) <= 0:
            continue
        out.append({
            "id": str(index),
            "name": str(device.get("name", f"Input {index}")),
            "channels": int(device.get("max_input_channels", 0)),
            "default_samplerate": float(device.get("default_samplerate", SAMPLE_RATE)),
        })
    return out


def record_until_silence(
    settings: VoiceSettings,
    mode: str = "hotkey",
    stop_event: threading.Event | None = None,
    level_callback: Callable[[float], None] | None = None,
) -> AudioCaptureResult:
    try:
        import sounddevice as sd
    except ImportError as error:
        raise RuntimeError("sounddevice is required for microphone recording") from error

    voice = settings.normalized()
    vad_settings = voice.vad
    silence_ms = vad_settings.continuous_silence_ms if mode == "continuous" else vad_settings.hotkey_silence_ms
    block_size = int(SAMPLE_RATE * vad_settings.block_ms / 1000)
    max_blocks = max(1, int(vad_settings.max_utterance_ms / vad_settings.block_ms))
    silence_blocks_needed = max(1, int(silence_ms / vad_settings.block_ms))
    device = _device_arg(voice.microphone_device)
    stop_event = stop_event or threading.Event()
    level_callback = level_callback or (lambda _level: None)
    vad = EnergyVad(vad_settings)

    frames: list[np.ndarray] = []
    speech_started = mode == "hotkey"
    silence_blocks = 0
    peak_rms = 0.0
    started_at = time.monotonic()

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=block_size,
        device=device,
    ) as stream:
        for _ in range(max_blocks):
            if stop_event.is_set():
                break

            block, _overflowed = stream.read(block_size)
            samples = np.asarray(block, dtype=np.float32).reshape(-1)
            decision = vad.decide(samples)
            peak_rms = max(peak_rms, decision.rms)
            level_callback(decision.rms)

            if decision.is_speech:
                speech_started = True
                silence_blocks = 0
            elif speech_started:
                silence_blocks += 1

            if speech_started:
                frames.append(samples.copy())

            if speech_started and silence_blocks >= silence_blocks_needed:
                break

    audio = np.concatenate(frames).astype(np.float32) if frames else np.zeros(0, dtype=np.float32)
    duration_ms = int((time.monotonic() - started_at) * 1000)
    return AudioCaptureResult(
        audio=audio,
        duration_ms=duration_ms,
        peak_rms=peak_rms,
        speech_detected=bool(frames) and peak_rms >= vad_settings.sensitivity,
    )


def record_fixed_seconds(
    settings: VoiceSettings,
    seconds: float = 3.0,
    level_callback: Callable[[float], None] | None = None,
) -> AudioCaptureResult:
    try:
        import sounddevice as sd
    except ImportError as error:
        raise RuntimeError("sounddevice is required for microphone recording") from error

    voice = settings.normalized()
    level_callback = level_callback or (lambda _level: None)
    samples_count = max(1, int(SAMPLE_RATE * seconds))
    device = _device_arg(voice.microphone_device)
    data = sd.rec(samples_count, samplerate=SAMPLE_RATE, channels=1, dtype="float32", device=device)
    sd.wait()
    audio = np.asarray(data, dtype=np.float32).reshape(-1)
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    level_callback(peak)
    return AudioCaptureResult(
        audio=audio,
        duration_ms=int(seconds * 1000),
        peak_rms=peak,
        speech_detected=peak >= voice.vad.sensitivity,
    )


def _device_arg(value: str):
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return value
