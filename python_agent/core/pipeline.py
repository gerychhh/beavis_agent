from __future__ import annotations

from uuid import uuid4

from python_agent.core.logger import ActionLogger
from python_agent.core.schemas import ArgsPrediction, PipelineOutput, SkillResult, ToolCall
from python_agent.cpp_client import CppClient, CppClientError
from python_agent.nlu.argument_extractors.base import ArgumentExtractor
from python_agent.nlu.argument_extractors.open_app import OpenAppExtractor
from python_agent.nlu.argument_extractors.volume_set import VolumeSetExtractor
from python_agent.nlu.argument_extractors.window_control import WindowControlExtractor
from python_agent.nlu.argument_extractors.window_layout import WindowLayoutExtractor
from python_agent.nlu.normalizer import Normalizer
from python_agent.nlu.skill_classifier import ModelSkillClassifier


class PipelineError(RuntimeError):
    pass


class CommandPipeline:
    def __init__(
        self,
        normalizer: Normalizer | None = None,
        skill_classifier: ModelSkillClassifier | None = None,
        extractors: dict[str, ArgumentExtractor] | None = None,
        cpp_client: CppClient | None = None,
        logger: ActionLogger | None = None,
    ) -> None:
        self.normalizer = normalizer or Normalizer()
        self.skill_classifier = skill_classifier or ModelSkillClassifier()
        self.extractors = extractors or {
            "open_app": OpenAppExtractor(),
            "volume_set": VolumeSetExtractor(),
            "window_control": WindowControlExtractor(),
            "window_layout": WindowLayoutExtractor(),
        }
        self.cpp_client = cpp_client or CppClient()
        self.logger = logger or ActionLogger()

    def build_tool_call(
        self,
        raw_text: str,
        source: str = "text",
        meta: dict[str, object] | None = None,
    ) -> PipelineOutput:
        normalized_text = self.normalizer.normalize(raw_text)
        skill_prediction = self.skill_classifier.predict(normalized_text)

        if skill_prediction.skill == "unknown":
            raise PipelineError(f"Unknown command: {raw_text}")

        extractor = self.extractors.get(skill_prediction.skill)
        if extractor is None:
            raise PipelineError(f"No extractor registered for skill: {skill_prediction.skill}")

        args_prediction = extractor.extract(normalized_text)
        if args_prediction.missing:
            missing = ", ".join(args_prediction.missing)
            raise PipelineError(f"Missing required arguments for {skill_prediction.skill}: {missing}")

        tool_meta: dict[str, object] = {
            "source": source,
            "raw_text": raw_text,
            "normalized_text": normalized_text,
            "skill_confidence": skill_prediction.confidence,
            "args_confidence": args_prediction.confidence,
        }
        if meta:
            tool_meta.update(meta)

        tool_call = ToolCall(
            request_id=self._new_request_id(),
            skill=skill_prediction.skill,
            args=args_prediction.args,
            meta=tool_meta,
        )

        return PipelineOutput(
            raw_text=raw_text,
            normalized_text=normalized_text,
            skill_prediction=skill_prediction,
            args_prediction=args_prediction,
            tool_call=tool_call,
        )

    def run(
        self,
        raw_text: str,
        execute: bool = False,
        log: bool = True,
        source: str = "text",
        meta: dict[str, object] | None = None,
    ) -> PipelineOutput:
        try:
            output = self.build_tool_call(raw_text, source=source, meta=meta)
        except PipelineError as error:
            if log:
                self.logger.log_command_error(
                    raw_text=raw_text,
                    message=str(error),
                    code="PIPELINE_ERROR",
                    source=source,
                    stage="build_tool_call",
                    skill="pipeline_error",
                    meta=dict(meta or {}),
                )
            raise

        execution_result = None
        if execute:
            try:
                result_payload = self.cpp_client.execute(output.tool_call.to_dict())
            except CppClientError as error:
                failure = SkillResult(
                    request_id=output.tool_call.request_id,
                    success=False,
                    skill=output.tool_call.skill,
                    message=str(error),
                    error={
                        "type": "cpp_runtime",
                        "details": str(error),
                    },
                )
                failed_output = PipelineOutput(
                    raw_text=output.raw_text,
                    normalized_text=output.normalized_text,
                    skill_prediction=output.skill_prediction,
                    args_prediction=output.args_prediction,
                    tool_call=output.tool_call,
                    execution_result=failure,
                )
                if log:
                    self.logger.log(failed_output, training_status="system_error")
                raise PipelineError(str(error)) from error

            execution_result = SkillResult.from_dict(result_payload)

        output = PipelineOutput(
            raw_text=output.raw_text,
            normalized_text=output.normalized_text,
            skill_prediction=output.skill_prediction,
            args_prediction=output.args_prediction,
            tool_call=output.tool_call,
            execution_result=execution_result,
        )

        if log:
            self.logger.log(output)

        return output

    def _new_request_id(self) -> str:
        return f"cmd_{uuid4().hex[:8]}"


def build_tool_call(raw_text: str) -> ToolCall:
    return CommandPipeline().build_tool_call(raw_text).tool_call
