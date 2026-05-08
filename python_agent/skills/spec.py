from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ArgSpec:
    name: str
    type: str
    required: bool = True
    values: list[str] | None = None
    min_value: int | float | None = None
    max_value: int | float | None = None
    description: str = ""


@dataclass(frozen=True)
class SkillSpec:
    name: str
    description: str
    risk: str
    extractor: Any
    args: list[ArgSpec]
    examples: list[dict[str, Any]] = field(default_factory=list)
