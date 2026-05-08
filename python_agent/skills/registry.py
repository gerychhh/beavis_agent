from __future__ import annotations

from python_agent.nlu.argument_extractors.base import ArgumentExtractor
from python_agent.nlu.argument_extractors.open_app import OpenAppExtractor
from python_agent.nlu.argument_extractors.volume_set import VolumeSetExtractor
from python_agent.nlu.argument_extractors.window_control import WindowControlExtractor
from python_agent.nlu.argument_extractors.window_layout import WindowLayoutExtractor
from python_agent.skills.spec import ArgSpec, SkillSpec


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, SkillSpec] = {}

    def register(self, spec: SkillSpec) -> None:
        if spec.name in self._skills:
            raise ValueError(f"Skill already registered: {spec.name}")
        self._skills[spec.name] = spec

    def get(self, name: str) -> SkillSpec:
        if name not in self._skills:
            raise KeyError(f"Unknown skill: {name}")
        return self._skills[name]

    def names(self) -> list[str]:
        return sorted(self._skills.keys())


def build_skill_registry(
    extractors: dict[str, ArgumentExtractor] | None = None,
) -> SkillRegistry:
    extractors = extractors or {
        "open_app": OpenAppExtractor(),
        "volume_set": VolumeSetExtractor(),
        "window_control": WindowControlExtractor(),
        "window_layout": WindowLayoutExtractor(),
    }

    registry = SkillRegistry()
    registry.register(
        SkillSpec(
            name="open_app",
            description="Open or focus a Windows application",
            risk="low",
            extractor=extractors["open_app"],
            args=[
                ArgSpec(name="app_id", type="string", required=True),
            ],
        )
    )
    registry.register(
        SkillSpec(
            name="volume_set",
            description="Set or change system volume",
            risk="low",
            extractor=extractors["volume_set"],
            args=[
                ArgSpec(name="mode", type="enum", required=True, values=["set", "delta"]),
                ArgSpec(name="percent", type="int", required=False, min_value=0, max_value=100),
                ArgSpec(name="delta", type="int", required=False, min_value=-100, max_value=100),
            ],
        )
    )
    registry.register(
        SkillSpec(
            name="window_control",
            description="Close, minimize, maximize, or restore a window",
            risk="medium",
            extractor=extractors["window_control"],
            args=[
                ArgSpec(
                    name="action",
                    type="enum",
                    required=True,
                    values=["close", "minimize", "maximize", "restore"],
                ),
                ArgSpec(name="target_type", type="enum", required=True, values=["app", "current"]),
                ArgSpec(name="app_id", type="string", required=False),
            ],
        )
    )
    registry.register(
        SkillSpec(
            name="window_layout",
            description="Move or arrange one or more windows",
            risk="medium",
            extractor=extractors["window_layout"],
            args=[
                ArgSpec(name="layout", type="string", required=True),
                ArgSpec(name="targets", type="list", required=True),
            ],
        )
    )
    return registry
