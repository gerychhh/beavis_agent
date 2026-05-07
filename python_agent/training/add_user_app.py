from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from python_agent.core.pipeline import CommandPipeline
from python_agent.resolvers.app_catalog_service import (
    AppCatalogService,
    AppRecord,
    DEFAULT_APPS_CATALOG_PATH,
)
from python_agent.resolvers.app_catalog_utils import (
    normalize_app_id,
    normalize_speech_forms,
    suggest_app_id,
)
from python_agent.resolvers.app_visibility import is_user_visible_app
from python_agent.resolvers.windows_app_discovery import discover_windows_apps


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_APPS_INDEX_PATH = PROJECT_ROOT / "python_agent" / "data" / "cache" / "apps_index.json"
ProgressCallback = Callable[[str], None]
CancelCallback = Callable[[], bool]
STANDARD_DEFAULT_APP_IDS = {
    # Microsoft Office
    "access",
    "database_compare",
    "excel",
    "office",
    "onenote",
    "outlook",
    "powerpoint",
    "project",
    "spreadsheet_compare",
    "visio",
    "word",
    # Adobe
    "acrobat_reader",
    "adobe_xd",
    "after_effects",
    "animate",
    "audition",
    "bridge",
    "illustrator",
    "indesign",
    "lightroom",
    "media_encoder",
    "photoshop",
    "premiere_pro",
    "substance_painter",
    # Windows shell/tools
    "calculator",
    "camera",
    "character_map",
    "cmd",
    "computer_management",
    "control_panel",
    "device_manager",
    "disk_cleanup",
    "disk_management",
    "edge",
    "event_viewer",
    "explorer",
    "game_bar",
    "magnify",
    "microsoft_store",
    "narrator",
    "notepad",
    "on_screen_keyboard",
    "paint",
    "performance_monitor",
    "photos",
    "powershell",
    "print_management",
    "regedit",
    "remote_desktop_connection",
    "resource_monitor",
    "run",
    "services",
    "settings",
    "snipping_tool",
    "steps_recorder",
    "system_configuration",
    "system_information",
    "task_manager",
    "task_scheduler",
    "terminal",
    "voice_recorder",
    "windows_defender_firewall_with_advanced_security",
    "windows_media_player_legacy",
    "wmplayer",
}


def _is_user_visible_app(record: AppRecord) -> bool:
    return is_user_visible_app(record)


@dataclass(frozen=True)
class AddUserAppRequest:
    display_name: str
    path: Path | None = None
    app_id: str | None = None
    speech_forms: list[str] = field(default_factory=list)
    windows_app_id: str | None = None
    launch_type: str = "apps_folder"
    launch_target: str | None = None
    retrain: bool = True
    catalog_path: Path = DEFAULT_APPS_CATALOG_PATH
    index_output_path: Path = DEFAULT_APPS_INDEX_PATH


@dataclass(frozen=True)
class AddUserAppResult:
    app: Any
    index_summary: dict[str, Any]
    commands: list[dict[str, Any]]
    smoke_results: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        app_payload = self.app.to_dict() if hasattr(self.app, "to_dict") else self.app
        return {
            "app": app_payload,
            "index_summary": self.index_summary,
            "commands": self.commands,
            "smoke_results": self.smoke_results,
        }


@dataclass(frozen=True)
class UpdateUserAppRequest:
    app_id: str
    speech_forms: list[str] = field(default_factory=list)
    retrain: bool = True
    catalog_path: Path = DEFAULT_APPS_CATALOG_PATH
    index_output_path: Path = DEFAULT_APPS_INDEX_PATH


@dataclass(frozen=True)
class DeleteUserAppRequest:
    app_id: str
    retrain: bool = True
    catalog_path: Path = DEFAULT_APPS_CATALOG_PATH
    index_output_path: Path = DEFAULT_APPS_INDEX_PATH


@dataclass(frozen=True)
class AppCatalogChange:
    operation: str
    source: str
    app_id: str
    display_name: str = ""
    speech_forms: list[str] = field(default_factory=list)
    path: Path | None = None
    windows_app_id: str | None = None
    launch_type: str = "apps_folder"
    launch_target: str | None = None


@dataclass(frozen=True)
class ApplyUserAppChangesRequest:
    changes: list[AppCatalogChange]
    retrain: bool = True
    catalog_path: Path = DEFAULT_APPS_CATALOG_PATH
    index_output_path: Path = DEFAULT_APPS_INDEX_PATH


@dataclass(frozen=True)
class SyncVisibleAppsRequest:
    apps: list[AppCatalogChange]
    retrain: bool = True
    catalog_path: Path = DEFAULT_APPS_CATALOG_PATH
    index_output_path: Path = DEFAULT_APPS_INDEX_PATH


@dataclass(frozen=True)
class ApplyUserAppChangesResult:
    changes: list[dict[str, Any]]
    index_summary: dict[str, Any]
    commands: list[dict[str, Any]]
    smoke_results: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "changes": self.changes,
            "index_summary": self.index_summary,
            "commands": self.commands,
            "smoke_results": self.smoke_results,
        }


class TrainingCancelled(RuntimeError):
    pass


def retrain_apps_pipeline(
    catalog_path: Path = DEFAULT_APPS_CATALOG_PATH,
    index_output_path: Path = DEFAULT_APPS_INDEX_PATH,
    progress: ProgressCallback | None = None,
    should_cancel: CancelCallback | None = None,
) -> dict[str, Any]:
    progress = progress or (lambda _message: None)
    should_cancel = should_cancel or (lambda: False)
    progress("Rebuilding runtime app index")
    if should_cancel():
        raise TrainingCancelled("Training cancelled before index rebuild")
    index_summary = rebuild_apps_index(catalog_path, index_output_path)
    progress("Training command pipeline")
    commands = _run_training(progress, catalog_path, should_cancel=should_cancel)
    progress("Training finished")
    return {
        "index_summary": index_summary,
        "commands": commands,
    }


def add_user_app(
    request: AddUserAppRequest,
    progress: ProgressCallback | None = None,
) -> AddUserAppResult:
    progress = progress or (lambda _message: None)

    progress("Проверяю приложение")
    record = _build_record(request)

    progress("Сохраняю приложение")
    service = AppCatalogService(request.catalog_path)
    existing = service.get_app(record.app_id)
    replace_existing = False
    if existing is not None:
        replace_existing = not existing.enabled or not _is_user_visible_app(existing)
        if not replace_existing:
            raise ValueError(f"app_id is already used: {record.app_id}")

    service.add_app(record, replace_existing=replace_existing)

    progress("Обновляю каталог")
    index_summary = rebuild_apps_index(request.catalog_path, request.index_output_path)

    commands: list[dict[str, Any]] = []
    smoke_results: list[dict[str, Any]] = []

    if request.retrain:
        commands.extend(_run_training(progress, request.catalog_path))

        progress("Проверяю новые фразы")
        smoke_results = smoke_check(record)
        _raise_if_smoke_failed(smoke_results, "New app smoke checks failed")

    progress("Готово")
    return AddUserAppResult(
        app=record,
        index_summary=index_summary,
        commands=commands,
        smoke_results=smoke_results,
    )


def apply_user_app_changes(
    request: ApplyUserAppChangesRequest,
    progress: ProgressCallback | None = None,
) -> ApplyUserAppChangesResult:
    progress = progress or (lambda _message: None)
    progress("Проверяю изменения")

    if not request.changes:
        raise ValueError("No app catalog changes to apply")

    service = AppCatalogService(request.catalog_path)
    applied: list[dict[str, Any]] = []
    smoke_records: list[AppRecord] = []
    normalized_changes: list[tuple[str, str, AppCatalogChange]] = []

    for raw_change in request.changes:
        operation = raw_change.operation.strip().lower()
        app_id = normalize_app_id(raw_change.app_id)

        if operation not in {"add", "update_speech_forms", "delete", "enable", "disable"}:
            raise ValueError(f"Unsupported app catalog operation: {raw_change.operation}")

        if operation != "add" and not app_id:
            raise ValueError("app_id is required")

        normalized_changes.append((operation, app_id, raw_change))

    removed_ids: set[str] = set()

    for operation, app_id, _raw_change in normalized_changes:
        if operation not in {"delete", "disable"}:
            continue

        record = service.get_app(app_id)
        if record is None:
            applied.append({"operation": "delete_missing", "source": "unknown", "app_id": app_id})
            removed_ids.add(app_id)
            continue

        deleted = service.delete_app(app_id)
        applied.append({"operation": "delete", "source": deleted.source, "app_id": app_id})
        removed_ids.add(app_id)

    for operation, app_id, raw_change in normalized_changes:
        if operation in {"delete", "disable"}:
            continue

        if operation == "add":
            record = _build_record(
                AddUserAppRequest(
                    path=raw_change.path,
                    display_name=raw_change.display_name,
                    app_id=app_id or None,
                    speech_forms=raw_change.speech_forms,
                    windows_app_id=raw_change.windows_app_id,
                    launch_type=raw_change.launch_type,
                    launch_target=raw_change.launch_target,
                    retrain=False,
                    catalog_path=request.catalog_path,
                )
            )

            existing = service.get_app(record.app_id)
            replace_existing = False
            if existing is not None:
                replace_existing = (
                    record.app_id in removed_ids
                    or not existing.enabled
                    or not _is_user_visible_app(existing)
                )
                if not replace_existing:
                    raise ValueError(f"app_id is already used: {record.app_id}")

            service.add_app(record, replace_existing=replace_existing)
            applied.append({"operation": "add", "source": "user", "app_id": record.app_id})
            smoke_records.append(record)
            continue

        record = service.get_app(app_id)
        if record is None:
            raise ValueError(f"app not found: {app_id}")

        if operation == "update_speech_forms":
            updated = service.update_app(
                app_id,
                speech_forms=normalize_speech_forms(raw_change.speech_forms),
            )
            applied.append({"operation": "update_speech_forms", "source": updated.source, "app_id": app_id})
            if updated.enabled:
                smoke_records.append(updated)
            continue

        if operation == "enable":
            forms = normalize_speech_forms(raw_change.speech_forms)
            if forms:
                enabled = service.update_app(app_id, enabled=True, speech_forms=forms)
            else:
                enabled = service.enable_app(app_id)
            applied.append({"operation": "enable", "source": enabled.source, "app_id": app_id})
            smoke_records.append(enabled)
            continue

    _compact_catalog_to_visible_user_apps(service)
    progress("Обновляю каталог")
    index_summary = rebuild_apps_index(request.catalog_path, request.index_output_path)
    index_summary["sync"] = verify_visible_catalog_runtime_sync(
        request.catalog_path,
        request.index_output_path,
    )

    commands: list[dict[str, Any]] = []
    smoke_results: list[dict[str, Any]] = []

    if request.retrain:
        commands.extend(_run_training(progress, request.catalog_path))

        progress("Проверяю новые фразы")
        checked_ids: set[str] = set()

        for record in smoke_records:
            if record.app_id in checked_ids:
                continue
            checked_ids.add(record.app_id)
            smoke_results.extend(smoke_check(record))

        _raise_if_smoke_failed(smoke_results, "App catalog smoke checks failed")

    progress("Готово")
    return ApplyUserAppChangesResult(
        changes=applied,
        index_summary=index_summary,
        commands=commands,
        smoke_results=smoke_results,
    )


def sync_visible_user_apps(
    request: SyncVisibleAppsRequest,
    progress: ProgressCallback | None = None,
) -> ApplyUserAppChangesResult:
    progress = progress or (lambda _message: None)
    progress("Синхронизирую список приложений")

    service = AppCatalogService(request.catalog_path)
    records: list[AppRecord] = []
    seen_ids: set[str] = set()

    for item in request.apps:
        app_id = normalize_app_id(item.app_id)
        record = _build_record(
            AddUserAppRequest(
                path=item.path,
                display_name=item.display_name,
                app_id=app_id or None,
                speech_forms=item.speech_forms,
                windows_app_id=item.windows_app_id,
                launch_type=item.launch_type,
                launch_target=item.launch_target,
                retrain=False,
                catalog_path=request.catalog_path,
            )
        )
        if record.app_id in seen_ids:
            raise ValueError(f"Duplicate app_id in visible apps snapshot: {record.app_id}")
        seen_ids.add(record.app_id)
        records.append(replace(record, source="user", enabled=True))

    service.save(records)
    progress("Обновляю каталог")
    index_summary = rebuild_apps_index(request.catalog_path, request.index_output_path)
    index_summary["sync"] = verify_visible_catalog_runtime_sync(
        request.catalog_path,
        request.index_output_path,
    )

    commands: list[dict[str, Any]] = []
    smoke_results: list[dict[str, Any]] = []
    if request.retrain:
        commands.extend(_run_training(progress, request.catalog_path))
        progress("Проверяю новые фразы")
        for record in records[:20]:
            smoke_results.extend(smoke_check(record))
        _raise_if_smoke_failed(smoke_results, "App catalog smoke checks failed")

    progress("Готово")
    return ApplyUserAppChangesResult(
        changes=[
            {"operation": "sync", "source": "user", "app_id": record.app_id}
            for record in records
        ],
        index_summary=index_summary,
        commands=commands,
        smoke_results=smoke_results,
    )


def delete_user_app(
    request: DeleteUserAppRequest,
    progress: ProgressCallback | None = None,
) -> AddUserAppResult:
    progress = progress or (lambda _message: None)

    service = AppCatalogService(request.catalog_path)
    record = service.get_app(request.app_id)

    if record is None:
        raise ValueError(f"app not found: {request.app_id}")

    progress("Удаляю приложение")
    if record.source == "user":
        changed_record = service.delete_user_app(record.app_id)
    else:
        changed_record = service.disable_app(record.app_id)

    progress("Обновляю каталог")
    index_summary = rebuild_apps_index(request.catalog_path, request.index_output_path)

    commands: list[dict[str, Any]] = []
    if request.retrain:
        commands.extend(_run_training(progress, request.catalog_path))

    progress("Готово")
    return AddUserAppResult(
        app=changed_record,
        index_summary=index_summary,
        commands=commands,
        smoke_results=[],
    )


def update_user_app(
    request: UpdateUserAppRequest,
    progress: ProgressCallback | None = None,
) -> AddUserAppResult:
    progress = progress or (lambda _message: None)

    progress("Сохраняю сленг")
    service = AppCatalogService(request.catalog_path)
    record = service.update_app(
        request.app_id,
        speech_forms=normalize_speech_forms(request.speech_forms),
    )

    progress("Обновляю каталог")
    index_summary = rebuild_apps_index(request.catalog_path, request.index_output_path)

    commands: list[dict[str, Any]] = []
    smoke_results: list[dict[str, Any]] = []

    if request.retrain:
        commands.extend(_run_training(progress, request.catalog_path))

        if record.enabled:
            progress("Проверяю новые фразы")
            smoke_results = smoke_check(record)
            _raise_if_smoke_failed(smoke_results, "Updated app smoke checks failed")

    progress("Готово")
    return AddUserAppResult(
        app=record,
        index_summary=index_summary,
        commands=commands,
        smoke_results=smoke_results,
    )


def _build_record(request: AddUserAppRequest) -> AppRecord:
    display_name = request.display_name.strip()
    if not display_name:
        raise ValueError("display_name is required")

    app_id = normalize_app_id(
        request.app_id
        or suggest_app_id(
            display_name,
            request.path or request.launch_target or request.windows_app_id,
        )
    )
    if not app_id:
        raise ValueError("app_id is required")

    if request.windows_app_id:
        windows_app_id = request.windows_app_id.strip()
        launch_type = (request.launch_type or "apps_folder").strip() or "apps_folder"
        launch_target = (request.launch_target or "").strip()
        if not launch_target:
            launch_target = f"shell:AppsFolder\\{windows_app_id}" if launch_type == "apps_folder" else windows_app_id
        target_path = windows_app_id
        working_directory = ""
    else:
        if request.path is None:
            raise ValueError("Application path or Windows app id is required")

        app_path = request.path.expanduser()
        if not app_path.exists() or not app_path.is_file():
            raise ValueError(f"Application path does not exist: {app_path}")

        if app_path.suffix.lower() != ".exe":
            raise ValueError("Only .exe applications are supported for this flow")

        launch_type = "exe"
        launch_target = str(app_path)
        target_path = str(app_path)
        working_directory = str(app_path.parent)

    return AppRecord(
        app_id=app_id,
        display_name=display_name,
        source="user",
        enabled=True,
        launch_type=launch_type,
        launch_target=launch_target,
        target_path=target_path,
        working_directory=working_directory,
        speech_forms=normalize_speech_forms(
            [
                display_name,
                Path(launch_target).stem if launch_target else "",
                Path(target_path).stem if target_path else "",
                *(request.speech_forms or []),
            ]
        ),
        priority=300,
    )


def rebuild_apps_index(
    catalog_path: Path = DEFAULT_APPS_CATALOG_PATH,
    output_path: Path = DEFAULT_APPS_INDEX_PATH,
) -> dict[str, Any]:
    service = AppCatalogService(catalog_path)
    apps = service.get_all_apps()
    enabled = [app for app in apps if app.enabled and _is_user_visible_app(app)]

    records: list[dict[str, Any]] = []
    for app in enabled:
        if not app.launch_target:
            continue

        records.append({
            "app_id": app.app_id,
            "display_name": app.display_name,
            "display_names": list(dict.fromkeys([app.display_name, *app.speech_forms])),
            "launch_type": app.launch_type,
            "launch_target": app.launch_target,
            "target_path": app.target_path or app.launch_target,
            "arguments": "",
            "working_directory": app.working_directory,
            "source": app.source,
            "exists": _index_target_exists(app.launch_type, app.launch_target),
            "priority": app.priority,
        })

    records.sort(key=lambda item: (
        str(item.get("app_id", "")),
        -int(item.get("priority", 0)),
        str(item.get("display_name", "")),
    ))

    output_path = Path(output_path)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    index = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "apps_catalog",
        "catalog_path": str(service.catalog_path),
        "records": records,
        "summary": {
            "records_total": len(records),
            "records_existing": sum(1 for record in records if record.get("exists")),
            "app_ids_total": len({record.get("app_id") for record in records}),
            "enabled_apps": len(enabled),
            "disabled_apps": len(apps) - len(enabled),
        },
    }
    output_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "source": "apps_catalog",
        "catalog_path": str(service.catalog_path),
        "index_path": str(output_path),
        "total_apps": len(apps),
        "enabled_apps": len(enabled),
        "disabled_apps": len(apps) - len(enabled),
        "runtime_records": len(records),
        "runtime_existing_records": index["summary"]["records_existing"],
    }


def _index_target_exists(launch_type: str, launch_target: str) -> bool:
    if not launch_target:
        return False
    if launch_type in {"apps_folder", "uri"}:
        return True
    return Path(launch_target).expanduser().exists()


def _run_training(
    progress: ProgressCallback,
    apps_catalog_path: Path,
    should_cancel: CancelCallback | None = None,
) -> list[dict[str, Any]]:
    apps_catalog_path = Path(apps_catalog_path)
    should_cancel = should_cancel or (lambda: False)
    worker_count = max(1, min(32, (os.cpu_count() or 4) - 1))
    training_env = {
        **os.environ,
        "OMP_NUM_THREADS": str(worker_count),
        "MKL_NUM_THREADS": str(worker_count),
        "OPENBLAS_NUM_THREADS": str(worker_count),
        "NUMEXPR_NUM_THREADS": str(worker_count),
        "BEAVIS_TRAINING_WORKERS": str(worker_count),
    }
    commands: list[tuple[str, list[str]]] = [
        (
            "Генерирую датасет open_app",
            [
                "python_agent.training.generate_open_app_dataset",
                "--apps-catalog-path", str(apps_catalog_path),
            ],
        ),
        (
            "Обучаю open_app",
            ["python_agent.training.train_open_app_arg_model"],
        ),
        (
            "Тестирую open_app",
            ["python_agent.training.test_open_app_arg_model"],
        ),
        (
            "Генерирую датасет window_control",
            [
                "python_agent.training.generate_window_control_dataset",
                "--apps-catalog-path", str(apps_catalog_path),
            ],
        ),
        (
            "Обучаю window_control",
            ["python_agent.training.train_window_control_arg_model"],
        ),
        (
            "Тестирую window_control",
            ["python_agent.training.test_window_control_arg_model"],
        ),
        (
            "Генерирую датасет window_layout",
            [
                "python_agent.training.generate_window_layout_dataset",
                "--apps-catalog-path", str(apps_catalog_path),
            ],
        ),
        (
            "Обучаю window_layout",
            ["python_agent.training.train_window_layout_arg_model"],
        ),
        (
            "Тестирую window_layout",
            ["python_agent.training.test_window_layout_arg_model"],
        ),
        (
            "Генерирую датасет skill_classifier",
            [
                "python_agent.training.generate_skill_classifier_dataset",
                "--apps-catalog-path", str(apps_catalog_path),
            ],
        ),
        (
            "Обучаю skill_classifier",
            ["python_agent.training.train_skill_classifier"],
        ),
        (
            "Тестирую skill_classifier",
            ["python_agent.training.test_skill_classifier"],
        ),
    ]

    results: list[dict[str, Any]] = []

    for title, module_args in commands:
        if should_cancel():
            raise TrainingCancelled(f"Training cancelled before step: {title}")
        progress(title)
        cmd = [sys.executable, "-m", *module_args]
        process = subprocess.Popen(
            cmd,
            cwd=PROJECT_ROOT,
            env=training_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        while process.poll() is None:
            if should_cancel():
                progress(f"Отменяю шаг: {title}")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                stdout, stderr = process.communicate()
                results.append({
                    "title": title,
                    "command": cmd,
                    "returncode": process.returncode,
                    "stdout": (stdout or "")[-6000:],
                    "stderr": (stderr or "")[-6000:],
                    "cancelled": True,
                })
                raise TrainingCancelled(f"Training cancelled during step: {title}")
            time.sleep(0.2)

        stdout, stderr = process.communicate()
        result = {
            "title": title,
            "command": cmd,
            "returncode": process.returncode,
            "stdout": (stdout or "")[-6000:],
            "stderr": (stderr or "")[-6000:],
        }
        results.append(result)

        if process.returncode != 0:
            raise RuntimeError(
                f"{title} failed with exit code {process.returncode}\n"
                f"STDOUT:\n{stdout}\n"
                f"STDERR:\n{stderr}"
            )

    return results


def _compact_catalog_to_visible_user_apps(service: AppCatalogService) -> None:
    visible_records = [
        replace(record, source="user", enabled=True)
        for record in service.get_all_apps()
        if record.enabled and _is_user_visible_app(record)
    ]
    service.save(visible_records)


def verify_visible_catalog_runtime_sync(
    catalog_path: Path = DEFAULT_APPS_CATALOG_PATH,
    index_output_path: Path = DEFAULT_APPS_INDEX_PATH,
) -> dict[str, Any]:
    visible_ids = {
        record["app_id"]
        for record in list_user_app_records(catalog_path)
    }
    if index_output_path.exists():
        payload = json.loads(index_output_path.read_text(encoding="utf-8"))
        runtime_ids = {
            str(record.get("app_id") or "")
            for record in payload.get("records", [])
            if record.get("app_id")
        }
    else:
        runtime_ids = set()

    missing_from_runtime = sorted(visible_ids - runtime_ids)
    extra_in_runtime = sorted(runtime_ids - visible_ids)
    return {
        "ok": not missing_from_runtime and not extra_in_runtime,
        "visible_app_ids": len(visible_ids),
        "runtime_app_ids": len(runtime_ids),
        "missing_from_runtime": missing_from_runtime,
        "extra_in_runtime": extra_in_runtime,
    }


def smoke_check(record: AppRecord) -> list[dict[str, Any]]:
    pipeline = CommandPipeline()

    surfaces = [record.display_name, *record.speech_forms]
    surfaces = list(dict.fromkeys([item for item in surfaces if item]))[:5]

    phrases: list[str] = []
    for surface in surfaces:
        phrases.extend([
            f"открой {surface}",
            f"запусти {surface}",
            f"{surface} открой",
        ])

    results = []
    for phrase in phrases[:9]:
        output = pipeline.run(phrase, execute=False, log=False)
        got_skill = output.skill_prediction.skill
        got_app_id = output.args_prediction.args.get("app_id")
        ok = got_skill == "open_app" and got_app_id == record.app_id
        results.append({
            "text": phrase,
            "skill": got_skill,
            "app_id": got_app_id,
            "ok": ok,
        })

    return results


def _raise_if_smoke_failed(smoke_results: list[dict[str, Any]], message: str) -> None:
    failed = [item for item in smoke_results if not item.get("ok")]
    if failed:
        raise RuntimeError(message + ": " + json.dumps(failed, ensure_ascii=False))


def list_user_app_records(catalog_path: Path = DEFAULT_APPS_CATALOG_PATH) -> list[dict[str, Any]]:
    service = AppCatalogService(catalog_path)
    records: list[dict[str, Any]] = []
    for record in service.get_all_apps():
        if not record.enabled:
            continue
        if not _is_user_visible_app(record):
            continue
        payload = record.to_dict()
        payload["source"] = "user"
        records.append(payload)
    return records


def list_windows_apps() -> list[dict[str, str]]:
    return [entry.to_dict() for entry in discover_windows_apps()]


def _parse_speech_forms(values: list[str]) -> list[str]:
    forms: list[str] = []
    for value in values:
        forms.extend(str(value).replace(",", "\n").splitlines())
    return normalize_speech_forms(forms)


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")

    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("--display-name", required=True)
    add_parser.add_argument("--path", type=Path, default=None)
    add_parser.add_argument("--app-id", default=None)
    add_parser.add_argument("--speech-form", action="append", default=[])
    add_parser.add_argument("--windows-app-id", default=None)
    add_parser.add_argument("--launch-type", default="apps_folder")
    add_parser.add_argument("--launch-target", default=None)
    add_parser.add_argument("--no-retrain", action="store_true")
    add_parser.add_argument("--apps-catalog-path", type=Path, default=DEFAULT_APPS_CATALOG_PATH)

    update_parser = subparsers.add_parser("update")
    update_parser.add_argument("--app-id", required=True)
    update_parser.add_argument("--speech-form", action="append", default=[])
    update_parser.add_argument("--no-retrain", action="store_true")
    update_parser.add_argument("--apps-catalog-path", type=Path, default=DEFAULT_APPS_CATALOG_PATH)

    delete_parser = subparsers.add_parser("delete")
    delete_parser.add_argument("--app-id", required=True)
    delete_parser.add_argument("--no-retrain", action="store_true")
    delete_parser.add_argument("--apps-catalog-path", type=Path, default=DEFAULT_APPS_CATALOG_PATH)

    subparsers.add_parser("list")
    subparsers.add_parser("windows")

    args = parser.parse_args()

    if args.command in {None, "add"}:
        if args.command is None:
            # Backward-friendly CLI shape:
            # python -m python_agent.training.add_user_app --display-name ... --path ...
            parser = argparse.ArgumentParser()
            parser.add_argument("--display-name", required=True)
            parser.add_argument("--path", type=Path, default=None)
            parser.add_argument("--app-id", default=None)
            parser.add_argument("--speech-form", action="append", default=[])
            parser.add_argument("--windows-app-id", default=None)
            parser.add_argument("--launch-type", default="apps_folder")
            parser.add_argument("--launch-target", default=None)
            parser.add_argument("--no-retrain", action="store_true")
            parser.add_argument("--apps-catalog-path", type=Path, default=DEFAULT_APPS_CATALOG_PATH)
            args = parser.parse_args()

        result = add_user_app(
            AddUserAppRequest(
                display_name=args.display_name,
                path=args.path,
                app_id=args.app_id,
                speech_forms=_parse_speech_forms(args.speech_form),
                windows_app_id=args.windows_app_id,
                launch_type=args.launch_type,
                launch_target=args.launch_target,
                retrain=not args.no_retrain,
                catalog_path=args.apps_catalog_path,
            ),
            progress=lambda message: print(message, file=sys.stderr),
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return

    if args.command == "update":
        result = update_user_app(
            UpdateUserAppRequest(
                app_id=args.app_id,
                speech_forms=_parse_speech_forms(args.speech_form),
                retrain=not args.no_retrain,
                catalog_path=args.apps_catalog_path,
            ),
            progress=lambda message: print(message, file=sys.stderr),
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return

    if args.command == "delete":
        result = delete_user_app(
            DeleteUserAppRequest(
                app_id=args.app_id,
                retrain=not args.no_retrain,
                catalog_path=args.apps_catalog_path,
            ),
            progress=lambda message: print(message, file=sys.stderr),
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return

    if args.command == "list":
        print(json.dumps(list_user_app_records(), ensure_ascii=False, indent=2))
        return

    if args.command == "windows":
        print(json.dumps(list_windows_apps(), ensure_ascii=False, indent=2))
        return


if __name__ == "__main__":
    main()
