from __future__ import annotations

from pathlib import Path

from python_agent.core.schemas import ArgsPrediction
from python_agent.nlu.argument_extractors.base import ArgumentExtractor
from python_agent.nlu.argument_extractors.window_control_model import WindowControlModelExtractor


class WindowControlExtractor(ArgumentExtractor):
    def __init__(
        self,
        model_path: str | Path | None = None,
        model_extractor: ArgumentExtractor | None = None,
    ) -> None:
        self.model_extractor = model_extractor or WindowControlModelExtractor(model_path=model_path)

    def extract(self, text: str) -> ArgsPrediction:
        return self.model_extractor.extract(text)

