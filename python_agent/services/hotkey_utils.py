"""Hotkey string normalization utilities (no Qt / Win32 dependency)."""
from __future__ import annotations

MODIFIER_ALIASES: dict[str, tuple[str, int]] = {
    "CTRL": ("Ctrl", 0x0002),
    "CONTROL": ("Ctrl", 0x0002),
    "ALT": ("Alt", 0x0001),
    "SHIFT": ("Shift", 0x0004),
    "WIN": ("Win", 0x0008),
    "META": ("Win", 0x0008),
    "SUPER": ("Win", 0x0008),
}

KEY_TO_VK: dict[str, int] = {
    "SPACE": 0x20, "ENTER": 0x0D, "RETURN": 0x0D, "TAB": 0x09,
    "ESC": 0x1B, "ESCAPE": 0x1B, "BACKSPACE": 0x08, "DELETE": 0x2E,
    "DEL": 0x2E, "INSERT": 0x2D, "INS": 0x2D, "HOME": 0x24,
    "END": 0x23, "PAGEUP": 0x21, "PAGEDOWN": 0x22,
    "UP": 0x26, "DOWN": 0x28, "LEFT": 0x25, "RIGHT": 0x27,
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73,
    "F5": 0x74, "F6": 0x75, "F7": 0x76, "F8": 0x77,
    "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
}


class HotkeyParseError(ValueError):
    pass


def normalize_hotkey_sequence(sequence: str) -> str:
    """Normalize a hotkey string like 'ctrl+alt+space' -> 'Ctrl+Alt+Space'."""
    parts = [part.strip() for part in sequence.replace(" ", "").split("+") if part.strip()]
    if len(parts) < 2:
        raise HotkeyParseError("Нужен хоткей с модификатором и клавишей")

    modifiers: dict[str, int] = {}
    key: str | None = None

    for part in parts:
        upper = part.upper()
        alias = MODIFIER_ALIASES.get(upper)
        if alias is not None:
            modifiers[alias[0]] = alias[1]
            continue

        if key is not None:
            raise HotkeyParseError("В хоткее должна быть только одна обычная клавиша")
        key = _normalize_key_name(part)

    if not modifiers:
        raise HotkeyParseError("Добавь Ctrl, Alt, Shift или Win")
    if key is None:
        raise HotkeyParseError("Не выбрана основная клавиша")

    ordered_modifiers = [
        name for name in ("Ctrl", "Alt", "Shift", "Win") if name in modifiers
    ]
    return "+".join([*ordered_modifiers, key])


def _normalize_key_name(value: str) -> str:
    key = value.strip()
    upper = key.upper()

    if len(upper) == 1 and ("A" <= upper <= "Z" or "0" <= upper <= "9"):
        return upper

    if upper in KEY_TO_VK:
        if upper == "ESC":
            return "Escape"
        if upper in ("RETURN", "ENTER"):
            return "Enter"
        if upper in ("DEL", "DELETE"):
            return "Delete"
        return key.capitalize()

    return key
