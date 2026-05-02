from __future__ import annotations

import threading
import traceback
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from python_agent.core.pipeline import CommandPipeline, PipelineError
from python_agent.core.schemas import PipelineOutput
from python_agent.voice.service import VoiceService
from python_agent.voice.settings import VoiceSettings
from python_agent.training.add_user_app import (
    AddUserAppRequest,
    DeleteUserAppRequest,
    UpdateUserAppRequest,
    add_user_app,
    delete_user_app,
    list_user_app_records,
    list_windows_apps,
    update_user_app,
)


class CommandTaskSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()


class CommandTask(QRunnable):
    def __init__(
        self,
        pipeline: CommandPipeline,
        text: str,
        execute: bool,
        source: str = "text",
        meta: dict[str, object] | None = None,
    ) -> None:
        super().__init__()
        self.pipeline = pipeline
        self.text = text
        self.execute = execute
        self.source = source
        self.meta = meta or {}
        self.signals = CommandTaskSignals()

    @Slot()
    def run(self) -> None:
        try:
            output = self.pipeline.run(
                self.text,
                execute=self.execute,
                log=True,
                source=self.source,
                meta=self.meta,
            )
        except PipelineError as error:
            self.signals.failed.emit(str(error))
        except Exception as error:  # pragma: no cover - last line of defense for UI.
            details = traceback.format_exception_only(type(error), error)
            self.signals.failed.emit("".join(details).strip())
        else:
            self.signals.succeeded.emit(output)
        finally:
            self.signals.finished.emit()


class UserAppTaskSignals(QObject):
    progress = Signal(str)
    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()


class UserAppTask(QRunnable):
    def __init__(
        self,
        display_name: str,
        app_id: str,
        speech_forms: list[str],
        path: str = "",
        windows_app_id: str = "",
        launch_type: str = "apps_folder",
        launch_target: str = "",
    ) -> None:
        super().__init__()
        self.path = path
        self.display_name = display_name
        self.app_id = app_id
        self.speech_forms = speech_forms
        self.windows_app_id = windows_app_id
        self.launch_type = launch_type
        self.launch_target = launch_target
        self.signals = UserAppTaskSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = add_user_app(
                AddUserAppRequest(
                    path=Path(self.path) if self.path else None,
                    display_name=self.display_name,
                    app_id=self.app_id or None,
                    speech_forms=self.speech_forms,
                    windows_app_id=self.windows_app_id or None,
                    launch_type=self.launch_type,
                    launch_target=self.launch_target or None,
                    retrain=True,
                ),
                progress=self.signals.progress.emit,
            )
        except Exception as error:  # pragma: no cover - UI background task boundary.
            details = traceback.format_exception_only(type(error), error)
            self.signals.failed.emit("".join(details).strip())
        else:
            self.signals.succeeded.emit(result)
        finally:
            self.signals.finished.emit()


class WindowsAppsTaskSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()


class WindowsAppsTask(QRunnable):
    def __init__(self) -> None:
        super().__init__()
        self.signals = WindowsAppsTaskSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.succeeded.emit(list_windows_apps())
        except Exception as error:  # pragma: no cover - UI background task boundary.
            details = traceback.format_exception_only(type(error), error)
            self.signals.failed.emit("".join(details).strip())
        finally:
            self.signals.finished.emit()


class UserAppsTask(QRunnable):
    def __init__(self) -> None:
        super().__init__()
        self.signals = WindowsAppsTaskSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.succeeded.emit(list_user_app_records())
        except Exception as error:  # pragma: no cover - UI background task boundary.
            details = traceback.format_exception_only(type(error), error)
            self.signals.failed.emit("".join(details).strip())
        finally:
            self.signals.finished.emit()


class UpdateUserAppTask(QRunnable):
    def __init__(self, app_id: str, speech_forms: list[str]) -> None:
        super().__init__()
        self.app_id = app_id
        self.speech_forms = speech_forms
        self.signals = UserAppTaskSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = update_user_app(
                UpdateUserAppRequest(
                    app_id=self.app_id,
                    speech_forms=self.speech_forms,
                    retrain=True,
                ),
                progress=self.signals.progress.emit,
            )
        except Exception as error:  # pragma: no cover - UI background task boundary.
            details = traceback.format_exception_only(type(error), error)
            self.signals.failed.emit("".join(details).strip())
        else:
            self.signals.succeeded.emit(result)
        finally:
            self.signals.finished.emit()


class DeleteUserAppTask(QRunnable):
    def __init__(self, app_id: str) -> None:
        super().__init__()
        self.app_id = app_id
        self.signals = UserAppTaskSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = delete_user_app(
                DeleteUserAppRequest(
                    app_id=self.app_id,
                    retrain=True,
                ),
                progress=self.signals.progress.emit,
            )
        except Exception as error:  # pragma: no cover - UI background task boundary.
            details = traceback.format_exception_only(type(error), error)
            self.signals.failed.emit("".join(details).strip())
        else:
            self.signals.succeeded.emit(result)
        finally:
            self.signals.finished.emit()


class CommandRunner(QObject):
    started = Signal(str)
    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, pipeline: CommandPipeline | None = None) -> None:
        super().__init__()
        self.pipeline = pipeline or CommandPipeline()
        self.thread_pool = QThreadPool(self)
        self.thread_pool.setMaxThreadCount(1)
        self._active_tasks: set[CommandTask] = set()

    def run_command(
        self,
        text: str,
        execute: bool = True,
        source: str = "text",
        meta: dict[str, object] | None = None,
    ) -> bool:
        command = text.strip()
        if not command:
            self.failed.emit("Пустая команда")
            return False

        task = CommandTask(self.pipeline, command, execute, source=source, meta=meta)
        task.signals.succeeded.connect(self._emit_success)
        task.signals.failed.connect(self.failed)
        task.signals.finished.connect(self.finished)
        task.signals.finished.connect(lambda task=task: self._active_tasks.discard(task))

        self._active_tasks.add(task)
        self.started.emit(command)
        self.thread_pool.start(task)
        return True

    def reload_pipeline(self) -> None:
        self.pipeline = CommandPipeline()

    @Slot(object)
    def _emit_success(self, output: PipelineOutput) -> None:
        self.succeeded.emit(output)


class VoiceTaskSignals(QObject):
    listening = Signal()
    processing = Signal()
    recognized = Signal(object)
    ignored = Signal(object)
    failed = Signal(str)
    finished = Signal()
    level = Signal(float)


class VoiceListenTask(QRunnable):
    def __init__(
        self,
        service: VoiceService,
        settings: VoiceSettings,
        mode: str,
        require_wake_word: bool,
        stop_event: threading.Event,
    ) -> None:
        super().__init__()
        self.service = service
        self.settings = settings
        self.mode = mode
        self.require_wake_word = require_wake_word
        self.stop_event = stop_event
        self.signals = VoiceTaskSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.listening.emit()
            result = self.service.listen_once(
                self.settings,
                mode=self.mode,
                require_wake_word=self.require_wake_word,
                stop_event=self.stop_event,
                level_callback=self.signals.level.emit,
                processing_callback=self.signals.processing.emit,
            )
            if result.ignored:
                self.signals.ignored.emit(result)
            else:
                self.signals.recognized.emit(result)
        except Exception as error:  # pragma: no cover - UI background task boundary.
            details = traceback.format_exception_only(type(error), error)
            self.signals.failed.emit("".join(details).strip())
        finally:
            self.signals.finished.emit()


class VoiceTestTask(QRunnable):
    def __init__(self, service: VoiceService, settings: VoiceSettings) -> None:
        super().__init__()
        self.service = service
        self.settings = settings
        self.signals = VoiceTaskSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.listening.emit()
            result = self.service.test_microphone(
                self.settings,
                seconds=3.0,
                level_callback=self.signals.level.emit,
                processing_callback=self.signals.processing.emit,
            )
            self.signals.recognized.emit(result)
        except Exception as error:  # pragma: no cover - UI background task boundary.
            details = traceback.format_exception_only(type(error), error)
            self.signals.failed.emit("".join(details).strip())
        finally:
            self.signals.finished.emit()


class VoiceContinuousTask(QRunnable):
    def __init__(
        self,
        service: VoiceService,
        settings: VoiceSettings,
        stop_event: threading.Event,
    ) -> None:
        super().__init__()
        self.service = service
        self.settings = settings
        self.stop_event = stop_event
        self.signals = VoiceTaskSignals()

    @Slot()
    def run(self) -> None:
        try:
            if self.settings.preload_model_on_startup:
                self.signals.processing.emit()
                self.service.preload(self.settings)

            while not self.stop_event.is_set():
                self.signals.listening.emit()
                result = self.service.listen_once(
                    self.settings,
                    mode="continuous",
                    require_wake_word=self.settings.require_wake_word_for_continuous,
                    stop_event=self.stop_event,
                    level_callback=self.signals.level.emit,
                    processing_callback=self.signals.processing.emit,
                )
                if self.stop_event.is_set():
                    break
                if result.ignored:
                    self.signals.ignored.emit(result)
                else:
                    self.signals.recognized.emit(result)
        except Exception as error:  # pragma: no cover - UI background task boundary.
            details = traceback.format_exception_only(type(error), error)
            self.signals.failed.emit("".join(details).strip())
        finally:
            self.signals.finished.emit()


class VoicePreloadTask(QRunnable):
    def __init__(self, service: VoiceService, settings: VoiceSettings) -> None:
        super().__init__()
        self.service = service
        self.settings = settings
        self.signals = VoiceTaskSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.processing.emit()
            self.service.preload(self.settings)
            self.signals.recognized.emit(None)
        except Exception as error:  # pragma: no cover - UI background task boundary.
            details = traceback.format_exception_only(type(error), error)
            self.signals.failed.emit("".join(details).strip())
        finally:
            self.signals.finished.emit()


class VoiceRunner(QObject):
    listening = Signal()
    processing = Signal()
    preloading = Signal()
    recognized = Signal(object)
    ignored = Signal(object)
    failed = Signal(str)
    finished = Signal()
    level = Signal(float)
    continuous_changed = Signal(bool)
    preloaded = Signal()

    def __init__(self, service: VoiceService | None = None) -> None:
        super().__init__()
        self.service = service or VoiceService()
        self.thread_pool = QThreadPool(self)
        self.thread_pool.setMaxThreadCount(1)
        self._active_tasks: set[VoiceListenTask | VoiceTestTask | VoiceContinuousTask | VoicePreloadTask] = set()
        self._stop_event = threading.Event()
        self._continuous_running = False

    @property
    def continuous_running(self) -> bool:
        return self._continuous_running

    def listen_once(self, settings: VoiceSettings) -> bool:
        if self._active_tasks:
            return False
        self._stop_event = threading.Event()
        task = VoiceListenTask(
            self.service,
            settings.normalized(),
            mode="hotkey",
            require_wake_word=False,
            stop_event=self._stop_event,
        )
        self._start_task(task)
        return True

    def test_microphone(self, settings: VoiceSettings) -> bool:
        if self._active_tasks:
            return False
        task = VoiceTestTask(self.service, settings.normalized())
        self._start_task(task)
        return True

    def start_continuous(self, settings: VoiceSettings) -> bool:
        if self._continuous_running:
            return True
        if self._active_tasks:
            return False
        self._stop_event = threading.Event()
        task = VoiceContinuousTask(self.service, settings.normalized(), self._stop_event)
        self._continuous_running = True
        self.continuous_changed.emit(True)
        self._start_task(task)
        return True

    def preload(self, settings: VoiceSettings) -> bool:
        if self._active_tasks:
            return False
        task = VoicePreloadTask(self.service, settings.normalized())
        self._start_task(task)
        return True

    def stop(self) -> None:
        self._stop_event.set()
        if self._continuous_running:
            self._continuous_running = False
            self.continuous_changed.emit(False)

    def _start_task(self, task: VoiceListenTask | VoiceTestTask | VoiceContinuousTask | VoicePreloadTask) -> None:
        task.signals.listening.connect(self.listening)
        if isinstance(task, VoicePreloadTask):
            task.signals.processing.connect(self.preloading)
            task.signals.recognized.connect(lambda _result: self.preloaded.emit())
        else:
            task.signals.processing.connect(self.processing)
            task.signals.recognized.connect(self.recognized)
        task.signals.ignored.connect(self.ignored)
        task.signals.failed.connect(self.failed)
        task.signals.finished.connect(self.finished)
        task.signals.level.connect(self.level)
        task.signals.finished.connect(lambda task=task: self._active_tasks.discard(task))
        task.signals.finished.connect(self._handle_task_finished)
        self._active_tasks.add(task)
        self.thread_pool.start(task)

    @Slot()
    def _handle_task_finished(self) -> None:
        if self._continuous_running and not self._active_tasks:
            self._continuous_running = False
            self.continuous_changed.emit(False)


class UserAppRunner(QObject):
    progress = Signal(str)
    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()
    windows_apps_loaded = Signal(object)
    windows_apps_failed = Signal(str)
    user_apps_loaded = Signal(object)
    user_apps_failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.thread_pool = QThreadPool(self)
        self.thread_pool.setMaxThreadCount(1)
        self._active_tasks: set[UserAppTask | WindowsAppsTask | UserAppsTask | UpdateUserAppTask | DeleteUserAppTask] = set()

    def add_app(
        self,
        display_name: str,
        app_id: str,
        speech_forms: list[str],
        path: str = "",
        windows_app_id: str = "",
        launch_type: str = "apps_folder",
        launch_target: str = "",
    ) -> bool:
        if not path.strip() and not windows_app_id.strip():
            self.failed.emit("Укажи путь к .exe или выбери приложение Windows")
            return False
        if not display_name.strip():
            self.failed.emit("Укажи название приложения")
            return False

        task = UserAppTask(
            display_name=display_name.strip(),
            app_id=app_id.strip(),
            speech_forms=speech_forms,
            path=path.strip(),
            windows_app_id=windows_app_id.strip(),
            launch_type=launch_type.strip() or "apps_folder",
            launch_target=launch_target.strip(),
        )
        task.signals.progress.connect(self.progress)
        task.signals.succeeded.connect(self.succeeded)
        task.signals.failed.connect(self.failed)
        task.signals.finished.connect(self.finished)
        task.signals.finished.connect(lambda task=task: self._active_tasks.discard(task))

        self._active_tasks.add(task)
        self.thread_pool.start(task)
        return True

    def update_app_speech_forms(self, app_id: str, speech_forms: list[str]) -> bool:
        if not app_id.strip():
            self.failed.emit("Выбери добавленное приложение")
            return False

        task = UpdateUserAppTask(app_id.strip(), speech_forms)
        task.signals.progress.connect(self.progress)
        task.signals.succeeded.connect(self.succeeded)
        task.signals.failed.connect(self.failed)
        task.signals.finished.connect(self.finished)
        task.signals.finished.connect(lambda task=task: self._active_tasks.discard(task))

        self._active_tasks.add(task)
        self.thread_pool.start(task)
        return True

    def delete_app(self, app_id: str) -> bool:
        if not app_id.strip():
            self.failed.emit("Выбери добавленное приложение")
            return False

        task = DeleteUserAppTask(app_id.strip())
        task.signals.progress.connect(self.progress)
        task.signals.succeeded.connect(self.succeeded)
        task.signals.failed.connect(self.failed)
        task.signals.finished.connect(self.finished)
        task.signals.finished.connect(lambda task=task: self._active_tasks.discard(task))

        self._active_tasks.add(task)
        self.thread_pool.start(task)
        return True

    def load_windows_apps(self) -> None:
        task = WindowsAppsTask()
        task.signals.succeeded.connect(self.windows_apps_loaded)
        task.signals.failed.connect(self.windows_apps_failed)
        task.signals.finished.connect(lambda task=task: self._active_tasks.discard(task))
        self._active_tasks.add(task)
        self.thread_pool.start(task)

    def load_user_apps(self) -> None:
        task = UserAppsTask()
        task.signals.succeeded.connect(self.user_apps_loaded)
        task.signals.failed.connect(self.user_apps_failed)
        task.signals.finished.connect(lambda task=task: self._active_tasks.discard(task))
        self._active_tasks.add(task)
        self.thread_pool.start(task)
