from __future__ import annotations

from abc import ABC, abstractmethod

from python_agent.core.schemas import ArgsPrediction


class ArgumentExtractor(ABC):
    @abstractmethod
    def extract(self, text: str) -> ArgsPrediction:
        raise NotImplementedError
