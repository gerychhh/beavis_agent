from __future__ import annotations

from dataclasses import replace

from python_agent.nlu.argument_extractors.base import ArgumentExtractor
from python_agent.skills.open_app.spec import SPEC as OPEN_APP
from python_agent.skills.spec import SkillSpec
from python_agent.skills.volume_set.spec import SPEC as VOLUME_SET
from python_agent.skills.window_control.spec import SPEC as WINDOW_CONTROL
from python_agent.skills.window_layout.spec import SPEC as WINDOW_LAYOUT


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
    registry = SkillRegistry()

    for spec in (OPEN_APP, VOLUME_SET, WINDOW_CONTROL, WINDOW_LAYOUT):
        if not spec.enabled:
            continue
        if extractors and spec.name in extractors:
            spec = replace(spec, extractor=extractors[spec.name])
        registry.register(spec)

    return registry
