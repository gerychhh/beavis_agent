from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable

from python_agent.voice import audio as audio_capture
from python_agent.voice.settings import VoiceSettings
from python_agent.voice.stt import TranscriptionResult, WhisperTranscriber
from python_agent.voice.wake_word import strip_wake_word


@dataclass(frozen=True)
class VoiceCommandResult:
    command_text: str
    transcript: str
    ignored: bool
    reason: str
    meta: dict[str, object]


class VoiceService:
    def __init__(
        self,
        transcriber: WhisperTranscriber | None = None,
    ) -> None:
        self.transcriber = transcriber or WhisperTranscriber()
        self.state = "idle"

    def preload(self, settings: VoiceSettings) -> None:
        self.state = "processing"
        self.transcriber.preload(settings.stt)
        self.state = "idle"

    def listen_once(
        self,
        settings: VoiceSettings,
        mode: str = "hotkey",
        require_wake_word: bool = False,
        stop_event: threading.Event | None = None,
        level_callback: Callable[[float], None] | None = None,
        processing_callback: Callable[[], None] | None = None,
    ) -> VoiceCommandResult:
        voice = settings.normalized()
        self.state = "listening"
        capture = audio_capture.record_until_silence(
            voice,
            mode=mode,
            stop_event=stop_event,
            level_callback=level_callback,
        )
        if not capture.speech_detected:
            self.state = "idle"
            return VoiceCommandResult(
                command_text="",
                transcript="",
                ignored=True,
                reason="speech_not_detected",
                meta={
                    "source": "voice",
                    "audio_duration_ms": capture.duration_ms,
                    "wake_word_matched": False,
                },
            )

        self.state = "processing"
        if processing_callback is not None:
            processing_callback()
        transcription = self.transcriber.transcribe(capture.audio, voice.stt)
        result = build_voice_command_result(
            transcription,
            voice,
            capture.duration_ms,
            capture.peak_rms,
            require_wake_word=require_wake_word,
        )
        self.state = "recognized" if not result.ignored else "idle"
        return result

    def test_microphone(
        self,
        settings: VoiceSettings,
        seconds: float = 3.0,
        level_callback: Callable[[float], None] | None = None,
        processing_callback: Callable[[], None] | None = None,
    ) -> VoiceCommandResult:
        voice = settings.normalized()
        self.state = "listening"
        capture = audio_capture.record_fixed_seconds(voice, seconds=seconds, level_callback=level_callback)
        self.state = "processing"
        if processing_callback is not None:
            processing_callback()
        transcription = self.transcriber.transcribe(capture.audio, voice.stt)
        result = build_voice_command_result(
            transcription,
            voice,
            capture.duration_ms,
            capture.peak_rms,
            require_wake_word=False,
            test_mode=True,
        )
        self.state = "idle"
        return result


def build_voice_command_result(
    transcription: TranscriptionResult,
    settings: VoiceSettings,
    audio_duration_ms: int,
    peak_rms: float,
    require_wake_word: bool,
    test_mode: bool = False,
) -> VoiceCommandResult:
    transcript = " ".join(transcription.text.strip().split())
    match = strip_wake_word(transcript, settings.agent_names)
    command_text = match.command_text if match.matched else transcript
    ignored = False
    reason = ""

    if not transcript:
        ignored = True
        reason = "empty_transcript"
    elif require_wake_word and not match.matched:
        ignored = True
        reason = "wake_word_missing"
    elif require_wake_word and not command_text:
        ignored = True
        reason = "command_after_wake_word_missing"

    meta: dict[str, object] = {
        "source": "voice",
        "transcript": transcript,
        "stt_model": transcription.model_size,
        "stt_device": transcription.device,
        "stt_compute_type": transcription.compute_type,
        "audio_duration_ms": audio_duration_ms,
        "peak_rms": peak_rms,
        "wake_word_matched": match.matched,
        "wake_word": match.matched_name,
        "voice_mode": "test" if test_mode else ("continuous" if require_wake_word else "hotkey"),
    }
    if transcription.confidence is not None:
        meta["stt_confidence"] = transcription.confidence

    return VoiceCommandResult(
        command_text=command_text,
        transcript=transcript,
        ignored=ignored,
        reason=reason,
        meta=meta,
    )
