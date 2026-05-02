from __future__ import annotations

import ctypes
import ctypes.wintypes
import sys

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal


WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
VK_SPACE = 0x20


KEY_TO_VK: dict[str, int] = {
    "SPACE": VK_SPACE,
    "ENTER": 0x0D,
    "RETURN": 0x0D,
    "TAB": 0x09,
    "ESC": 0x1B,
    "ESCAPE": 0x1B,
    "BACKSPACE": 0x08,
    "DELETE": 0x2E,
    "DEL": 0x2E,
    "INSERT": 0x2D,
    "INS": 0x2D,
    "HOME": 0x24,
    "END": 0x23,
    "PAGEUP": 0x21,
    "PAGEDOWN": 0x22,
    "UP": 0x26,
    "DOWN": 0x28,
    "LEFT": 0x25,
    "RIGHT": 0x27,
}

for index in range(1, 25):
    KEY_TO_VK[f"F{index}"] = 0x70 + index - 1

MODIFIER_ALIASES: dict[str, tuple[str, int]] = {
    "CTRL": ("Ctrl", MOD_CONTROL),
    "CONTROL": ("Ctrl", MOD_CONTROL),
    "ALT": ("Alt", MOD_ALT),
    "SHIFT": ("Shift", MOD_SHIFT),
    "WIN": ("Win", MOD_WIN),
    "META": ("Win", MOD_WIN),
}


class HotkeyParseError(ValueError):
    pass


def normalize_hotkey_sequence(sequence: str) -> str:
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
        name for name in ("Ctrl", "Alt", "Shift", "Win")
        if name in modifiers
    ]
    return "+".join([*ordered_modifiers, key])


def parse_hotkey_sequence(sequence: str) -> tuple[int, int, str]:
    normalized = normalize_hotkey_sequence(sequence)
    modifiers = MOD_NOREPEAT
    virtual_key = 0

    for part in normalized.split("+"):
        alias = MODIFIER_ALIASES.get(part.upper())
        if alias is not None:
            modifiers |= alias[1]
        else:
            virtual_key = _key_to_vk(part)

    if virtual_key == 0:
        raise HotkeyParseError("Не удалось определить клавишу")

    return modifiers, virtual_key, normalized


def _normalize_key_name(value: str) -> str:
    key = value.strip()
    upper = key.upper()

    if len(upper) == 1 and ("A" <= upper <= "Z" or "0" <= upper <= "9"):
        return upper

    if upper in KEY_TO_VK:
        if upper == "ESC":
            return "Escape"
        if upper == "RETURN":
            return "Enter"
        if upper == "DEL":
            return "Delete"
        if upper == "INS":
            return "Insert"
        return upper[:1] + upper[1:].lower()

    raise HotkeyParseError(f"Клавиша не поддерживается: {value}")


def _key_to_vk(key: str) -> int:
    upper = key.upper()
    if len(upper) == 1 and ("A" <= upper <= "Z" or "0" <= upper <= "9"):
        return ord(upper)

    return KEY_TO_VK.get(upper, 0)


class WindowsHotkeyService(QObject, QAbstractNativeEventFilter):
    activated = Signal()

    def __init__(
        self,
        hotkey_id: int = 0xBEEA,
        modifiers: int = MOD_CONTROL | MOD_ALT | MOD_NOREPEAT,
        virtual_key: int = VK_SPACE,
    ) -> None:
        QObject.__init__(self)
        QAbstractNativeEventFilter.__init__(self)
        self.hotkey_id = hotkey_id
        self.modifiers = modifiers
        self.virtual_key = virtual_key
        self._registered = False

    @property
    def is_supported(self) -> bool:
        return sys.platform == "win32"

    @property
    def is_registered(self) -> bool:
        return self._registered

    def register(self) -> bool:
        if not self.is_supported:
            return False

        user32 = ctypes.windll.user32
        ok = user32.RegisterHotKey(
            None,
            self.hotkey_id,
            self.modifiers,
            self.virtual_key,
        )
        if not ok:
            raise RuntimeError(f"Не удалось зарегистрировать hotkey: {ctypes.FormatError()}")

        self._registered = True
        return True

    def unregister(self) -> None:
        if self._registered and self.is_supported:
            ctypes.windll.user32.UnregisterHotKey(None, self.hotkey_id)
        self._registered = False

    def nativeEventFilter(self, event_type: bytes | bytearray | str, message: int):
        if not self._registered or not self.is_supported:
            return False, 0

        try:
            msg = ctypes.wintypes.MSG.from_address(int(message))
        except (TypeError, ValueError):
            return False, 0

        if msg.message == WM_HOTKEY and int(msg.wParam) == self.hotkey_id:
            self.activated.emit()
            return True, 0

        return False, 0
