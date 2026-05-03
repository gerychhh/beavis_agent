from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from python_agent.ui.main_window import BeavisMainWindow
from python_agent.ui.settings_store import UiSettings
from python_agent.ui.workers import CommandRunner, UserAppRunner


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication(sys.argv[:1])
    window = BeavisMainWindow(
        CommandRunner(),
        user_app_runner=UserAppRunner(),
        settings=UiSettings(),
        hotkey_locked=True,
        autoload=False,
    )

    labels = [button.text() for button in window.nav_buttons]
    checks = {
        "tabs": labels == ["Главная", "Приложения", "История", "Настройки"],
        "voice_settings": (
            hasattr(window, "voice_mode_combo")
            and hasattr(window, "voice_hotkey_editor")
            and hasattr(window, "microphone_device_combo")
            and hasattr(window, "stt_model_combo")
            and hasattr(window, "stt_timeout_input")
        ),
        "apps_catalog": hasattr(window, "apps_catalog_table") and window.apps_catalog_table.rowCount() > 0,
        "new_app_dialog_unlocks": False,
        "new_app_dialog_buttons": False,
        "edit_dialog_locks": False,
        "edit_dialog_buttons": False,
        "builtin_edit_dialog": False,
        "edit_saves_pending": False,
        "delete_saves_pending": False,
        "same_id_replacement_pending": False,
    }

    fake_app = {
        "display_name": "My Tool",
        "app_id": "my_tool",
        "launch_type": "exe",
        "speech_forms": ["мой тул"],
    }
    window._open_add_app_dialog()
    app.processEvents()
    checks["new_app_dialog_unlocks"] = not window.app_display_name_input.isReadOnly() and not window.app_id_input.isReadOnly()
    checks["new_app_dialog_buttons"] = (
        window.add_app_button.isVisible()
        and window.add_app_button.text() == "Сохранить в черновик"
        and not window.update_app_button.isVisible()
        and not window.delete_app_button.isVisible()
    )
    if window._active_app_dialog is not None:
        window._active_app_dialog.close()
        app.processEvents()

    window._open_edit_app_dialog(fake_app)
    app.processEvents()
    checks["edit_dialog_locks"] = window.app_display_name_input.isReadOnly() and window.app_id_input.isReadOnly()
    checks["edit_dialog_buttons"] = (
        not window.add_app_button.isVisible()
        and window.update_app_button.isVisible()
        and window.update_app_button.text() == "Сохранить в черновик"
        and window.delete_app_button.isVisible()
        and window.delete_app_button.text() == "Удалить"
    )
    if window._active_app_dialog is not None:
        window._active_app_dialog.close()
        app.processEvents()

    builtin_app = {
        "display_name": "chrome",
        "app_id": "chrome",
        "source": "builtin",
        "custom_speech_forms": ["мой браузер"],
    }
    window._open_edit_app_dialog(builtin_app)
    app.processEvents()
    checks["builtin_edit_dialog"] = (
        window.app_id_input.text() == "chrome"
        and window.app_speech_forms_input.toPlainText().strip() == "мой браузер"
        and not window.add_app_button.isVisible()
    )
    window.app_speech_forms_input.setPlainText("мой новый браузер")
    window._submit_update_user_app()
    app.processEvents()
    pending = window._pending_app_changes.get("chrome")
    checks["edit_saves_pending"] = (
        pending is not None
        and pending.get("operation") == "update_speech_forms"
        and pending.get("source") == "builtin"
        and pending.get("speech_forms") == ["мой новый браузер"]
        and window.apply_app_changes_button.isEnabled()
    )
    if window._active_app_dialog is not None:
        window._active_app_dialog.close()
        app.processEvents()

    window._discard_pending_app_changes()
    window._open_edit_app_dialog(builtin_app)
    app.processEvents()
    window._submit_delete_user_app()
    app.processEvents()
    pending = window._pending_app_changes.get("chrome")
    checks["delete_saves_pending"] = (
        pending is not None
        and pending.get("operation") == "delete"
        and pending.get("source") == "builtin"
        and window.apply_app_changes_button.isEnabled()
    )
    window._discard_pending_app_changes()

    window._queue_pending_app_change({
        "operation": "delete",
        "source": "builtin",
        "app_id": "chrome",
        "display_name": "chrome",
        "speech_forms": [],
    }, close_dialog=False)
    window._queue_pending_app_change({
        "operation": "add",
        "source": "user",
        "app_id": "chrome",
        "display_name": "Custom Chrome",
        "path": r"C:\Temp\chrome.exe",
        "launch_type": "exe",
        "speech_forms": ["мой хром"],
    }, close_dialog=False)
    replacement_ops = [
        item.get("operation")
        for item in window._pending_app_changes.values()
        if item.get("app_id") == "chrome"
    ]
    checks["same_id_replacement_pending"] = replacement_ops == ["delete", "add"]
    window._discard_pending_app_changes()

    failed = [name for name, ok in checks.items() if not ok]
    print(json.dumps({"checks": checks, "failed": failed}, ensure_ascii=False, indent=2))
    app.quit()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
