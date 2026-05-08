from __future__ import annotations

from uuid import uuid4

from python_agent.core.command_executor import CommandExecutor
from python_agent.core.decision import CommandDecision
from python_agent.core.logger import ActionLogger
from python_agent.core.schemas import PipelineOutput, ToolCall
from python_agent.cpp_client import CppClient
from python_agent.nlu.argument_extractors.base import ArgumentExtractor
from python_agent.nlu.normalizer import Normalizer
from python_agent.nlu.skill_classifier import ModelSkillClassifier
from python_agent.skills.registry import SkillRegistry, build_skill_registry


class PipelineError(RuntimeError):
    pass


class CommandPipeline:
    def __init__(
        self,
        normalizer: Normalizer | None = None,
        skill_classifier: ModelSkillClassifier | None = None,
        extractors: dict[str, ArgumentExtractor] | None = None,
        skill_registry: SkillRegistry | None = None,
        cpp_client: CppClient | None = None,
        executor: CommandExecutor | None = None,
        logger: ActionLogger | None = None,
    ) -> None:
        self.normalizer = normalizer or Normalizer()
        self.skill_classifier = skill_classifier or ModelSkillClassifier()
        self.skill_registry = skill_registry or build_skill_registry(extractors=extractors)
        self.extractors = {
            name: self.skill_registry.get(name).extractor
            for name in self.skill_registry.names()
        }
        self.executor = executor or CommandExecutor(cpp_client=cpp_client)
        self.cpp_client = self.executor.cpp_client
        self.logger = logger or ActionLogger()

    def build(
        self,
        raw_text: str,
        source: str = "text",
        meta: dict[str, object] | None = None,
    ) -> CommandDecision:
        decision, _output = self._understand(raw_text, source=source, meta=meta)
        return decision

    def build_tool_call(
        self,
        raw_text: str,
        source: str = "text",
        meta: dict[str, object] | None = None,
    ) -> PipelineOutput:
        decision, output = self._understand(raw_text, source=source, meta=meta)
        if decision.status != "ready" or output is None:
            raise PipelineError(self._decision_error_message(decision))
        return output

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
            execution_result = self.executor.execute(output.tool_call)

        output = PipelineOutput(
            raw_text=output.raw_text,
            normalized_text=output.normalized_text,
            skill_prediction=output.skill_prediction,
            args_prediction=output.args_prediction,
            tool_call=output.tool_call,
            execution_result=execution_result,
        )

        if log:
            training_status = (
                "system_error"
                if execution_result is not None and not execution_result.success
                else "candidate"
            )
            self.logger.log(output, training_status=training_status)

        return output

    def _understand(
        self,
        raw_text: str,
        source: str,
        meta: dict[str, object] | None,
    ) -> tuple[CommandDecision, PipelineOutput | None]:
        normalized_text = self.normalizer.normalize(raw_text)
        try:
            skill_prediction = self.skill_classifier.predict(normalized_text)
        except Exception as error:
            return (
                CommandDecision(
                    status="error",
                    raw_text=raw_text,
                    normalized_text=normalized_text,
                    reason="skill_classifier_error",
                    debug={"error": f"{type(error).__name__}: {error}"},
                ),
                None,
            )

        skill_debug = skill_prediction.to_dict()
        if skill_prediction.skill == "unknown":
            return (
                CommandDecision(
                    status="rejected",
                    raw_text=raw_text,
                    normalized_text=normalized_text,
                    reason="unknown_command",
                    debug={"skill_prediction": skill_debug},
                ),
                None,
            )

        try:
            skill_spec = self.skill_registry.get(skill_prediction.skill)
        except KeyError:
            return (
                CommandDecision(
                    status="error",
                    raw_text=raw_text,
                    normalized_text=normalized_text,
                    reason="unknown_registered_skill",
                    debug={"skill_prediction": skill_debug},
                ),
                None,
            )

        try:
            args_prediction = skill_spec.extractor.extract(normalized_text)
        except Exception as error:
            return (
                CommandDecision(
                    status="error",
                    raw_text=raw_text,
                    normalized_text=normalized_text,
                    reason="args_extractor_error",
                    debug={
                        "skill_prediction": skill_debug,
                        "error": f"{type(error).__name__}: {error}",
                    },
                ),
                None,
            )

        args_debug = args_prediction.to_dict()
        if args_prediction.missing:
            missing = ", ".join(args_prediction.missing)
            return (
                CommandDecision(
                    status="needs_clarification",
                    raw_text=raw_text,
                    normalized_text=normalized_text,
                    reason="missing_args",
                    question=f"Missing required arguments for {skill_prediction.skill}: {missing}",
                    debug={
                        "skill_prediction": skill_debug,
                        "args_prediction": args_debug,
                    },
                ),
                None,
            )

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
        output = PipelineOutput(
            raw_text=raw_text,
            normalized_text=normalized_text,
            skill_prediction=skill_prediction,
            args_prediction=args_prediction,
            tool_call=tool_call,
        )
        return (
            CommandDecision(
                status="ready",
                raw_text=raw_text,
                normalized_text=normalized_text,
                tool_call=tool_call,
                debug={
                    "skill_prediction": skill_debug,
                    "args_prediction": args_debug,
                },
            ),
            output,
        )

    def _decision_error_message(self, decision: CommandDecision) -> str:
        if decision.reason == "unknown_command":
            return f"Unknown command: {decision.raw_text}"
        if decision.reason == "missing_args" and decision.question:
            return decision.question
        if decision.reason == "unknown_registered_skill":
            skill = decision.debug.get("skill_prediction", {}).get("skill")
            return f"No extractor registered for skill: {skill}"
        if decision.reason:
            return decision.reason
        return f"Command decision is not ready: {decision.status}"

    def _new_request_id(self) -> str:
        return f"cmd_{uuid4().hex[:8]}"


def build_tool_call(raw_text: str) -> ToolCall:
    return CommandPipeline().build_tool_call(raw_text).tool_call
