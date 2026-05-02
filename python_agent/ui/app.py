from __future__ import annotations

import argparse
import ctypes
import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import QApplication, QSystemTrayIcon


if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from python_agent.core.schemas import PipelineOutput
from python_agent.ui.formatting import output_title
from python_agent.ui.history_store import CommandHistoryStore
from python_agent.ui.hotkeys import HotkeyParseError, WindowsHotkeyService, parse_hotkey_sequence
from python_agent.ui.icons import beavis_icon
from python_agent.ui.main_window import BeavisMainWindow
from python_agent.ui.overlay_window import OverlayCommandWindow, VoiceOverlayWindow
from python_agent.ui.settings_store import UiSettings, UiSettingsStore
from python_agent.ui.toast import ToastWindow
from python_agent.ui.tray import BeavisTrayIcon
from python_agent.ui.workers import CommandRunner, UserAppRunner, VoiceRunner


TEXT_HOTKEY_ID = 0xBEEA
VOICE_HOTKEY_ID = 0xBEEB


@dataclass
class BeavisUiRuntime:
    app: QApplication
    runner: CommandRunner
    user_app_runner: UserAppRunner
    voice_runner: VoiceRunner
    main_window: BeavisMainWindow
    overlay: OverlayCommandWindow
    voice_overlay: VoiceOverlayWindow
    toast: ToastWindow
    tray: BeavisTrayIcon | None
    hotkey: WindowsHotkeyService | None
    voice_hotkey: WindowsHotkeyService | None
    settings_store: UiSettingsStore
    history_store: CommandHistoryStore


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Beavis Agent desktop UI")
    parser.add_argument("--hidden", action="store_true", help="Start in the tray")
    parser.add_argument("--no-hotkey", action="store_true", help="Disable global hotkeys")
    return parser.parse_args(argv)


def create_runtime(argv: list[str] | None = None) -> BeavisUiRuntime:
    args = parse_args(argv)
    _set_windows_app_id()

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("Beavis Agent")
    app.setWindowIcon(beavis_icon())
    app.setQuitOnLastWindowClosed(False)

    settings_store = UiSettingsStore()
    settings = settings_store.load()
    history_store = CommandHistoryStore()
    runner = CommandRunner()
    user_app_runner = UserAppRunner()
    voice_runner = VoiceRunner()
    main_window = BeavisMainWindow(
        runner,
        user_app_runner=user_app_runner,
        history_store=history_store,
        settings=settings,
        hotkey_locked=args.no_hotkey,
    )
    overlay = OverlayCommandWindow()
    voice_overlay = VoiceOverlayWindow()
    toast = ToastWindow()
    hotkey: WindowsHotkeyService | None = None
    voice_hotkey: WindowsHotkeyService | None = None

    runtime = BeavisUiRuntime(
        app=app,
        runner=runner,
        user_app_runner=user_app_runner,
        voice_runner=voice_runner,
        main_window=main_window,
        overlay=overlay,
        voice_overlay=voice_overlay,
        toast=toast,
        tray=None,
        hotkey=hotkey,
        voice_hotkey=voice_hotkey,
        settings_store=settings_store,
        history_store=history_store,
    )

    def show_main() -> None:
        main_window.show_front()

    def show_overlay() -> None:
        overlay.show_centered()

    def start_voice_hotkey() -> None:
        current = settings_store.load()
        if voice_runner.listen_once(current.voice):
            voice_overlay.show_centered("Слушаю", "Говори команду")

    def quit_app() -> None:
        _unregister_hotkey(app, runtime.hotkey)
        _unregister_hotkey(app, runtime.voice_hotkey)
        voice_runner.stop()
        app.quit()

    def apply_settings(new_settings: UiSettings) -> None:
        nonlocal settings

        _unregister_hotkey(app, runtime.hotkey)
        _unregister_hotkey(app, runtime.voice_hotkey)
        runtime.hotkey = None
        runtime.voice_hotkey = None
        voice_runner.stop()

        try:
            settings_store.save(new_settings)
            settings = settings_store.load()
        except ValueError as error:
            main_window.set_hotkey_status(str(error), ok=False)
            return

        if args.no_hotkey:
            main_window.set_hotkey_status("Хоткеи отключены параметром запуска", ok=False)
            return

        text_status = "Текстовый hotkey выключен"
        voice_status = "Голосовой hotkey выключен"

        if settings.text_hotkey_enabled:
            try:
                runtime.hotkey = _register_hotkey(app, settings.text_hotkey_sequence, show_overlay, TEXT_HOTKEY_ID)
                text_status = f"Текст: {settings.text_hotkey_sequence}"
            except (HotkeyParseError, RuntimeError) as error:
                text_status = str(error)

        if settings.voice.hotkey_enabled and settings.voice.mode == "hotkey":
            try:
                runtime.voice_hotkey = _register_hotkey(app, settings.voice.hotkey_sequence, start_voice_hotkey, VOICE_HOTKEY_ID)
                voice_status = f"Голос: {settings.voice.hotkey_sequence}"
            except (HotkeyParseError, RuntimeError) as error:
                voice_status = str(error)
        elif settings.voice.mode == "continuous":
            voice_status = "Голос: фоновое прослушивание"

        if settings.voice.mode == "continuous":
            if voice_runner.start_continuous(settings.voice):
                main_window.set_voice_status("Фоновое прослушивание активно", "Скажи имя агента перед командой")
        else:
            main_window.set_voice_status("Голос по hotkey", settings.voice.hotkey_sequence if settings.voice.mode != "off" else "Выключен")
            if settings.voice.preload_model_on_startup and settings.voice.mode != "off":
                voice_runner.preload(settings.voice)

        main_window.set_hotkey_status(f"{text_status} · {voice_status}", ok=True)

    if QSystemTrayIcon.isSystemTrayAvailable():
        runtime.tray = BeavisTrayIcon(app, show_main, show_overlay, quit_app)
        runtime.tray.show()

    overlay.submitted.connect(lambda text: runner.run_command(text, execute=True))
    voice_overlay.cancelled.connect(voice_runner.stop)
    main_window.settings_changed.connect(apply_settings)
    main_window.voice_test_requested.connect(lambda: voice_runner.test_microphone(settings_store.load().voice))

    runner.succeeded.connect(lambda output: _show_success_toast(toast, output))
    runner.failed.connect(lambda message: toast.show_message(message, success=False))

    voice_runner.listening.connect(lambda: main_window.set_voice_status("Слушаю", "Говори команду"))
    voice_runner.listening.connect(lambda: voice_overlay.set_message("Слушаю", "Говори команду"))
    voice_runner.processing.connect(lambda: main_window.set_voice_status("Распознаю", "Whisper обрабатывает речь"))
    voice_runner.processing.connect(lambda: voice_overlay.set_message("Распознаю", "Whisper обрабатывает речь"))
    voice_runner.preloading.connect(lambda: main_window.set_voice_status("Готовлю голосовую модель", "Whisper загружается в фоне"))
    voice_runner.preloaded.connect(lambda: main_window.set_voice_status("Голос готов", settings_store.load().voice.hotkey_sequence))
    voice_runner.level.connect(voice_overlay.set_level)
    voice_runner.level.connect(main_window.set_voice_level)
    voice_runner.recognized.connect(lambda result: _handle_voice_recognized(runtime, result))
    voice_runner.ignored.connect(lambda result: _handle_voice_ignored(runtime, result))
    voice_runner.failed.connect(lambda message: _handle_voice_failed(runtime, message))
    voice_runner.finished.connect(lambda: voice_overlay.hide() if not voice_runner.continuous_running else None)

    apply_settings(settings)

    if not args.hidden:
        main_window.show_front()

    return runtime


def _register_hotkey(
    app: QApplication,
    sequence: str,
    callback,
    hotkey_id: int,
) -> WindowsHotkeyService:
    modifiers, virtual_key, _ = parse_hotkey_sequence(sequence)
    hotkey = WindowsHotkeyService(hotkey_id=hotkey_id, modifiers=modifiers, virtual_key=virtual_key)
    app.installNativeEventFilter(hotkey)
    hotkey.activated.connect(callback)
    hotkey.register()
    return hotkey


def _unregister_hotkey(app: QApplication, hotkey: WindowsHotkeyService | None) -> None:
    if hotkey is None:
        return
    hotkey.unregister()
    app.removeNativeEventFilter(hotkey)


def _set_windows_app_id() -> None:
    if sys.platform != "win32":
        return

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Beavis.Agent")
    except Exception:
        pass


def _show_success_toast(toast: ToastWindow, output: PipelineOutput) -> None:
    result = output.execution_result
    success = result.success if result is not None else True
    toast.show_message(output_title(output), success=success)


def _handle_voice_recognized(runtime: BeavisUiRuntime, result) -> None:
    runtime.voice_overlay.hide()
    runtime.main_window.set_voice_status("Распознано", result.command_text)
    runtime.runner.run_command(
        result.command_text,
        execute=True,
        source="voice",
        meta=dict(result.meta),
    )


def _handle_voice_ignored(runtime: BeavisUiRuntime, result) -> None:
    message = "Голос проигнорирован"
    if getattr(result, "reason", "") == "wake_word_missing":
        message = "Имя агента не найдено"
    elif getattr(result, "reason", "") == "empty_transcript":
        message = "Речь не распознана"
    elif getattr(result, "reason", "") == "speech_not_detected":
        message = "Речь не обнаружена"

    runtime.main_window.set_voice_status(message, getattr(result, "transcript", ""))
    if not runtime.voice_runner.continuous_running:
        runtime.toast.show_message(message, success=False)


def _handle_voice_failed(runtime: BeavisUiRuntime, message: str) -> None:
    runtime.voice_overlay.hide()
    runtime.main_window.set_voice_status("Ошибка голосового ввода", message)
    runtime.toast.show_message(message, success=False)


def main(argv: list[str] | None = None) -> int:
    runtime = create_runtime(argv)
    return runtime.app.exec()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
