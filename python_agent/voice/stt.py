from __future__ import annotations

import math
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from python_agent.voice.audio import SAMPLE_RATE
from python_agent.voice.settings import SttSettings


@dataclass(frozen=True)
class ResolvedSttRuntime:
    model_size: str
    device: str
    compute_type: str


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    confidence: float | None
    language: str
    duration: float
    model_size: str
    device: str
    compute_type: str


class WhisperTranscriber:
    def __init__(self) -> None:
        self._model: Any | None = None
        self._runtime: ResolvedSttRuntime | None = None
        self._lock = threading.Lock()
        self._busy = False

    def preload(self, settings: SttSettings) -> None:
        stt = settings.normalized()
        self._run_with_timeout(lambda: self._load_model(stt), stt.transcribe_timeout_s)

    def transcribe(self, audio: np.ndarray, settings: SttSettings) -> TranscriptionResult:
        timeout_s = settings.normalized().transcribe_timeout_s
        return self._run_with_timeout(lambda: self._transcribe_sync(audio, settings), timeout_s)

    def _transcribe_sync(self, audio: np.ndarray, settings: SttSettings) -> TranscriptionResult:
        if audio.size == 0:
            runtime = resolve_runtime(settings)
            return TranscriptionResult("", None, settings.language, 0.0, runtime.model_size, runtime.device, runtime.compute_type)

        model, runtime = self._load_model(settings)
        segments, info = model.transcribe(
            audio,
            language=settings.language,
            beam_size=settings.beam_size,
            vad_filter=settings.vad_filter,
            condition_on_previous_text=settings.condition_on_previous_text,
            temperature=settings.temperature,
        )
        segment_list = list(segments)
        text = " ".join(segment.text.strip() for segment in segment_list if segment.text.strip())
        confidence = _average_confidence(segment_list)
        duration = float(getattr(info, "duration", 0.0) or (audio.size / SAMPLE_RATE))
        language = str(getattr(info, "language", settings.language) or settings.language)
        return TranscriptionResult(
            text=" ".join(text.split()),
            confidence=confidence,
            language=language,
            duration=duration,
            model_size=runtime.model_size,
            device=runtime.device,
            compute_type=runtime.compute_type,
        )

    def _run_with_timeout(self, operation, timeout_s: float):
        with self._lock:
            if self._busy:
                raise RuntimeError("Whisper still processes the previous phrase")
            self._busy = True

        result: dict[str, object] = {}
        done = threading.Event()

        def worker() -> None:
            try:
                result["value"] = operation()
            except BaseException as error:  # pragma: no cover - worker boundary.
                result["error"] = error
            finally:
                with self._lock:
                    self._busy = False
                done.set()

        thread = threading.Thread(target=worker, name="beavis-whisper", daemon=True)
        thread.start()
        if not done.wait(timeout_s):
            raise TimeoutError(f"Whisper распознаёт дольше лимита: {timeout_s:.0f} сек")

        if "error" in result:
            raise result["error"]  # type: ignore[misc]
        return result["value"]

    def _load_model(self, settings: SttSettings):
        runtime = resolve_runtime(settings)
        if self._model is not None and self._runtime == runtime:
            return self._model, runtime

        try:
            from faster_whisper import WhisperModel
        except ImportError as error:
            raise RuntimeError(
                "faster-whisper or one of its dependencies is missing. "
                "Run: python -m pip install -r requirements.txt"
            ) from error

        model_dir = Path(settings.model_dir).expanduser()
        model_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._model = _create_model(WhisperModel, runtime, model_dir)
        except Exception:
            if runtime.device != "cuda":
                raise

            cpu_runtime = ResolvedSttRuntime(runtime.model_size, "cpu", "int8")
            try:
                self._model = _create_model(WhisperModel, cpu_runtime, model_dir)
                runtime = cpu_runtime
            except Exception:
                fallback_runtime = ResolvedSttRuntime("small", "cpu", "int8")
                self._model = _create_model(WhisperModel, fallback_runtime, model_dir)
                runtime = fallback_runtime

        self._runtime = runtime
        return self._model, runtime


def resolve_runtime(settings: SttSettings) -> ResolvedSttRuntime:
    stt = settings.normalized()
    if stt.profile == "custom":
        return ResolvedSttRuntime(
            stt.model_size,
            "cpu" if stt.device == "auto" else stt.device,
            "int8" if stt.compute_type == "auto" else stt.compute_type,
        )
    if stt.profile == "turbo":
        if cuda_available():
            return ResolvedSttRuntime("turbo", "cuda", "float16")
        return ResolvedSttRuntime("turbo", "cpu", "int8")
    if stt.profile == "cpu":
        return ResolvedSttRuntime("small", "cpu", "int8")
    if stt.profile == "accuracy":
        return ResolvedSttRuntime("medium", "cuda" if cuda_available() else "cpu", "float16" if cuda_available() else "int8")
    if cuda_available():
        return ResolvedSttRuntime("turbo", "cuda", "float16")
    return ResolvedSttRuntime("small", "cpu", "int8")


def _create_model(whisper_model, runtime: ResolvedSttRuntime, model_dir: Path):
    return whisper_model(
        runtime.model_size,
        device=runtime.device,
        compute_type=runtime.compute_type,
        download_root=str(model_dir),
    )


def cuda_available() -> bool:
    try:
        import ctranslate2

        count = getattr(ctranslate2, "get_cuda_device_count", lambda: 0)()
        return int(count) > 0
    except Exception:
        return False


def _average_confidence(segments: list[Any]) -> float | None:
    values: list[float] = []
    for segment in segments:
        avg_logprob = getattr(segment, "avg_logprob", None)
        if avg_logprob is None:
            continue
        try:
            values.append(max(0.0, min(1.0, math.exp(float(avg_logprob)))))
        except (TypeError, ValueError, OverflowError):
            continue
    if not values:
        return None
    return sum(values) / len(values)
