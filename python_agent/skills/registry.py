from __future__ import annotations

from python_agent.nlu.argument_extractors.base import ArgumentExtractor
from python_agent.skills.open_app.examples import EXAMPLES as OPEN_APP_EXAMPLES
from python_agent.skills.open_app.extractor import OpenAppExtractor
from python_agent.skills.open_app.spec import SPEC as OPEN_APP_SPEC
from python_agent.skills.spec import SkillSpec
from python_agent.skills.volume_set.examples import EXAMPLES as VOLUME_SET_EXAMPLES
from python_agent.skills.volume_set.extractor import VolumeSetExtractor
from python_agent.skills.volume_set.spec import SPEC as VOLUME_SET_SPEC
from python_agent.skills.web_open.examples import EXAMPLES as WEB_OPEN_EXAMPLES
from python_agent.skills.web_open.extractor import WebOpenExtractor
from python_agent.skills.web_open.spec import SPEC as WEB_OPEN_SPEC
from python_agent.skills.web_search.examples import EXAMPLES as WEB_SEARCH_EXAMPLES
from python_agent.skills.web_search.extractor import WebSearchExtractor
from python_agent.skills.web_search.spec import SPEC as WEB_SEARCH_SPEC
from python_agent.skills.window_control.examples import EXAMPLES as WINDOW_CONTROL_EXAMPLES
from python_agent.skills.window_control.extractor import WindowControlExtractor
from python_agent.skills.window_control.spec import SPEC as WINDOW_CONTROL_SPEC
from python_agent.skills.window_layout.examples import EXAMPLES as WINDOW_LAYOUT_EXAMPLES
from python_agent.skills.window_layout.extractor import WindowLayoutExtractor
from python_agent.skills.window_layout.spec import SPEC as WINDOW_LAYOUT_SPEC


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

    for spec in _fresh_specs():
        if not spec.enabled:
            continue
        if extractors and spec.name in extractors:
            spec = _copy_spec_with_extractor(spec, extractors[spec.name])
        registry.register(spec)

    return registry


def _fresh_specs() -> tuple[SkillSpec, ...]:
    return (
        _copy_spec_with_extractor(
            _copy_spec_with_examples(OPEN_APP_SPEC, OPEN_APP_EXAMPLES),
            OpenAppExtractor(),
        ),
        _copy_spec_with_extractor(
            _copy_spec_with_examples(VOLUME_SET_SPEC, VOLUME_SET_EXAMPLES),
            VolumeSetExtractor(),
        ),
        _copy_spec_with_extractor(
            _copy_spec_with_examples(WEB_OPEN_SPEC, WEB_OPEN_EXAMPLES),
            WebOpenExtractor(),
        ),
        _copy_spec_with_extractor(
            _copy_spec_with_examples(WEB_SEARCH_SPEC, WEB_SEARCH_EXAMPLES),
            WebSearchExtractor(),
        ),
        _copy_spec_with_extractor(
            _copy_spec_with_examples(WINDOW_CONTROL_SPEC, WINDOW_CONTROL_EXAMPLES),
            WindowControlExtractor(),
        ),
        _copy_spec_with_extractor(
            _copy_spec_with_examples(WINDOW_LAYOUT_SPEC, WINDOW_LAYOUT_EXAMPLES),
            WindowLayoutExtractor(),
        ),
    )


def _copy_spec_with_examples(spec: SkillSpec, examples: list[dict]) -> SkillSpec:
    return SkillSpec(
        name=spec.name,
        description=spec.description,
        risk=spec.risk,
        extractor=spec.extractor,
        args=list(spec.args),
        examples=examples,
        enabled=spec.enabled,
    )


def _copy_spec_with_extractor(spec: SkillSpec, extractor: ArgumentExtractor) -> SkillSpec:
    return SkillSpec(
        name=spec.name,
        description=spec.description,
        risk=spec.risk,
        extractor=extractor,
        args=list(spec.args),
        examples=list(spec.examples),
        enabled=spec.enabled,
    )
