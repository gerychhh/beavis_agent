from __future__ import annotations

from typing import Any

from python_agent.api.result import ok, fail
from python_agent.core.pipeline import CommandPipeline, PipelineError


class CommandsApi:
    """
    Stable API for command execution.

    UI should call this layer instead of importing CommandPipeline directly.
    Internally this still uses the existing CommandPipeline.
    """

    def __init__(self, pipeline: CommandPipeline | None = None) -> None:
        self.pipeline = pipeline or CommandPipeline()

    def build_tool_call(
        self,
        text: str,
        source: str = "text",
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            output = self.pipeline.build_tool_call(
                text,
                source=source,
                meta=meta,
            )
            return ok(output.to_dict())
        except PipelineError as error:
            return fail(error, code="PIPELINE_ERROR")
        except Exception as error:
            return fail(error, code="COMMAND_API_ERROR")

    def build_decision(
        self,
        text: str,
        source: str = "text",
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            decision = self.pipeline.build(
                text,
                source=source,
                meta=meta,
            )
            return ok(decision.to_dict())
        except Exception as error:
            return fail(error, code="COMMAND_API_ERROR")

    def run(
        self,
        text: str,
        execute: bool = True,
        log: bool = True,
        source: str = "text",
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            output = self.pipeline.run(
                raw_text=text,
                execute=execute,
                log=log,
                source=source,
                meta=meta,
            )
            return ok(output.to_dict())
        except PipelineError as error:
            return fail(error, code="PIPELINE_ERROR")
        except Exception as error:
            return fail(error, code="COMMAND_API_ERROR")

    def reload(self) -> dict[str, Any]:
        """Recreate pipeline instance after retraining or config/catalog changes."""
        try:
            self.pipeline = CommandPipeline()
            return ok({"reloaded": True})
        except Exception as error:
            return fail(error, code="COMMAND_API_RELOAD_ERROR")
