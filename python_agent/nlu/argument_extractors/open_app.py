from __future__ import annotations

from pathlib import Path

from python_agent.core.schemas import ArgsPrediction
from python_agent.nlu.argument_extractors.base import ArgumentExtractor
from python_agent.nlu.argument_extractors.open_app_model import OpenAppModelExtractor


class OpenAppExtractor(ArgumentExtractor):
    def __init__(
        self,
        model_path: str | Path | None = None,
        model_extractor: ArgumentExtractor | None = None,
    ) -> None:
        self.model_extractor = model_extractor or OpenAppModelExtractor(model_path=model_path)

    def extract(self, text: str) -> ArgsPrediction:
        return self.model_extractor.extract(text)
