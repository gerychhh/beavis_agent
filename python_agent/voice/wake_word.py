from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WakeWordMatch:
    matched: bool
    command_text: str
    matched_name: str = ""


def normalize_text(text: str) -> str:
    return " ".join(text.lower().replace(",", " ").replace(".", " ").split())


def strip_wake_word(text: str, agent_names: tuple[str, ...] | list[str], max_prefix_tokens: int = 3) -> WakeWordMatch:
    normalized = normalize_text(text)
    if not normalized:
        return WakeWordMatch(False, "")

    names = sorted(
        {normalize_text(name) for name in agent_names if normalize_text(name)},
        key=len,
        reverse=True,
    )

    for name in names:
        if normalized == name:
            return WakeWordMatch(True, "", name)
        if normalized.startswith(name + " "):
            return WakeWordMatch(True, normalized[len(name):].strip(), name)

    tokens = normalized.split()
    prefix = " ".join(tokens[:max_prefix_tokens])
    for name in names:
        index = prefix.find(name)
        if index < 0:
            continue
        tail = normalized[index + len(name):].strip()
        return WakeWordMatch(True, tail, name)

    return WakeWordMatch(False, normalized)
