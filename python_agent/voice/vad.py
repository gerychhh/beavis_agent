from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np

from python_agent.voice.settings import VadSettings


@dataclass(frozen=True)
class VadDecision:
    is_speech: bool
    rms: float


class EnergyVad:
    def __init__(self, settings: VadSettings | None = None) -> None:
        self.settings = (settings or VadSettings()).normalized()

    def decide(self, audio: np.ndarray) -> VadDecision:
        rms = rms_level(audio)
        return VadDecision(is_speech=rms >= self.settings.sensitivity, rms=rms)


def rms_level(audio: np.ndarray | Iterable[float]) -> float:
    data = np.asarray(list(audio) if not isinstance(audio, np.ndarray) else audio, dtype=np.float32)
    if data.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(data))))


def has_speech(audio: np.ndarray, settings: VadSettings | None = None) -> bool:
    return EnergyVad(settings).decide(audio).is_speech
