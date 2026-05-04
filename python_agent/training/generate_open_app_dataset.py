from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from python_agent.core.pipeline import CommandPipeline
from python_agent.resolvers import app_indexer
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
from python_agent.resolvers.windows_app_discovery import discover_windows_apps


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_APP_OVERRIDES_PATH = PROJECT_ROOT / "python_agent" / "data" / "user_apps" / "catalog_overrides.json"

ProgressCallback = Callable[[str], None]


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
    index_output_path: Path = app_indexer.DEFAULT_OUTPUT_PATH
    overrides_path: Path = DEFAULT_APP_OVERRIDES_PATH


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
    index_output_path: Path = app_indexer.DEFAULT_OUTPUT_PATH
    overrides_path: Path = DEFAULT_APP_OVERRIDES_PATH


@dataclass(frozen=True)
class DeleteUserAppRequest:
    app_id: str
    retrain: bool = True
    catalog_path: Path = DEFAULT_APPS_CATALOG_PATH
    index_output_path: Path = app_indexer.DEFAULT_OUTPUT_PATH
    overrides_path: Path = DEFAULT_APP_OVERRIDES_PATH


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
    index_output_path: Path = app_indexer.DEFAULT_OUTPUT_PATH
    overrides_path: Path = DEFAULT_APP_OVERRIDES_PATH


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


def add_user_app(
    request: AddUserAppRequest,
    progress: ProgressCallback | None = None,
) -> AddUserAppResult:
    progress = progress or (lambda _message: None)

    progress("Проверяю приложение")
    record = _build_record(request)

    progress("Сохраняю приложение")
    service = AppCatalogService(request.catalog_path)
    service.add_app(record, replace_existing=False)

    progress("Обновляю индекс")
    index_summary = rebuild_apps_index(
        request.catalog_path,
        request.index_output_path,
        request.overrides_path,
    )

    commands: list[dict[str, Any]] = []
    smoke_results: list[dict[str, Any]] = []

    if request.retrain:
        commands.extend(_run_training(progress, request.catalog_path, request.overrides_path))

    progress("Проверяю новые фразы")
    smoke_results = smoke_check(record)
    failed_smoke = [item for item in smoke_results if not item["ok"]]

    if failed_smoke:
        raise RuntimeError(
            "New app smoke checks failed: "
            + json.dumps(failed_smoke, ensure_ascii=False)
        )

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

    for raw_change in request.changes:
        operation = raw_change.operation.strip().lower()
        app_id = normalize_app_id(raw_change.app_id)

        if operation not in {"add", "update_speech_forms", "delete", "enable", "disable"}:
            raise ValueError(f"Unsupported app catalog operation: {raw_change.operation}")

        if operation != "add" and not app_id:
            raise ValueError("app_id is required")

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
                    index_output_path=request.index_output_path,
                    overrides_path=request.overrides_path,
                )
            )

            if service.get_app(record.app_id) is not None:
                raise ValueError(f"app_id is already used: {record.app_id}")

            service.add_app(record, replace_existing=False)
            applied.append({"operation": "add", "source": "user", "app_id": record.app_id})
            smoke_records.append(record)
            continue

        record = service.get_app(app_id)
        if record is None:
            raise ValueError(f"app not found: {app_id}")

        if operation == "update_speech_forms":
            forms = normalize_speech_forms(raw_change.speech_forms)
            updated = service.update_app(app_id, speech_forms=forms)
            applied.append({"operation": "update_speech_forms", "source": updated.source, "app_id": app_id})
            if updated.enabled:
                smoke_records.append(updated)
            continue

        if operation == "delete":
            if record.source == "user":
                deleted = service.delete_user_app(app_id)
                applied.append({"operation": "delete", "source": deleted.source, "app_id": app_id})
            else:
                disabled = service.disable_app(app_id)
                applied.append({"operation": "disable", "source": disabled.source, "app_id": app_id})
            continue

        if operation == "disable":
            disabled = service.disable_app(app_id)
            applied.append({"operation": "disable", "source": disabled.source, "app_id": app_id})
            continue

        if operation == "enable":
            enabled = service.enable_app(app_id)
            applied.append({"operation": "enable", "source": enabled.source, "app_id": app_id})
            smoke_records.append(enabled)
            continue

    progress("Обновляю индекс")
    index_summary = rebuild_apps_index(
        request.catalog_path,
        request.index_output_path,
        request.overrides_path,
    )

    commands: list[dict[str, Any]] = []
    smoke_results: list[dict[str, Any]] = []

    if request.retrain:
        commands.extend(_run_training(progress, request.catalog_path, request.overrides_path))

        progress("Проверяю новые фразы")
        checked_ids: set[str] = set()

        for record in smoke_records:
            if record.app_id in checked_ids:
                continue
            checked_ids.add(record.app_id)
            smoke_results.extend(smoke_check(record))

        failed_smoke = [item for item in smoke_results if not item["ok"]]
        if failed_smoke:
            raise RuntimeError(
                "App catalog smoke checks failed: "
                + json.dumps(failed_smoke, ensure_ascii=False)
            )

    progress("Готово")

    return ApplyUserAppChangesResult(
        changes=applied,
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

    progress("Обновляю индекс")
    index_summary = rebuild_apps_index(
        request.catalog_path,
        request.index_output_path,
        request.overrides_path,
    )

    commands: list[dict[str, Any]] = []

    if request.retrain:
        commands.extend(_run_training(progress, request.catalog_path, request.overrides_path))

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

    progress("Обновляю индекс")
    index_summary = rebuild_apps_index(
        request.catalog_path,
        request.index_output_path,
        request.overrides_path,
    )

    commands: list[dict[str, Any]] = []
    smoke_results: list[dict[str, Any]] = []

    if request.retrain:
        commands.extend(_run_training(progress, request.catalog_path, request.overrides_path))

    if record.enabled:
        progress("Проверяю новые фразы")
        smoke_results = smoke_check(record)
        failed_smoke = [item for item in smoke_results if not item["ok"]]

        if failed_smoke:
            raise RuntimeError(
                "Updated app smoke checks failed: "
                + json.dumps(failed_smoke, ensure_ascii=False)
            )

    progress("Готово")

    return AddUserAppResult(
        app=record,
        index_summary=index_summary,
        commands=commands,
        smoke_results=smoke_results,
    )


def _build_record(request: AddUserAppRequest) -> AppRecord:
    app_id = normalize_app_id(
        request.app_id
        or suggest_app_id(
            request.display_name,
            request.path or request.launch_target or request.windows_app_id,
        )
    )

    if not request.display_name.strip():
        raise ValueError("display_name is required")

    if request.windows_app_id:
        launch_type = request.launch_type or "apps_folder"
        launch_target = request.launch_target or request.windows_app_id
        target_path = request.windows_app_id
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
        display_name=request.display_name.strip(),
        source="user",
        enabled=True,
        launch_type=launch_type,
        launch_target=launch_target,
        target_path=target_path,
        working_directory=working_directory,
        speech_forms=normalize_speech_forms(
            [
                request.display_name,
                Path(launch_target).stem if launch_target else "",
                *request.speech_forms,
            ]
        ),
        priority=300,
    )


def rebuild_apps_index(
    user_catalog_path: Path = DEFAULT_APPS_CATALOG_PATH,
    output_path: Path = app_indexer.DEFAULT_OUTPUT_PATH,
    overrides_path: Path = DEFAULT_APP_OVERRIDES_PATH,
) -> dict[str, Any]:
    service = AppCatalogService(user_catalog_path)
    apps = service.get_enabled_apps()

    return {
        "source": "apps_catalog",
        "enabled_apps": len(apps),
        "catalog_path": str(service.catalog_path),
    }


def list_windows_apps() -> list[dict[str, str]]:
    return [entry.to_dict() for entry in discover_windows_apps()]


def list_user_app_records(catalog_path: Path = DEFAULT_APPS_CATALOG_PATH) -> list[dict[str, Any]]:
    service = AppCatalogService(catalog_path)
    return [record.to_dict() for record in service.get_all_apps()]


def _is_user_app(app_id: str, catalog_path: Path = DEFAULT_APPS_CATALOG_PATH) -> bool:
    service = AppCatalogService(catalog_path)
    record = service.get_app(app_id)
    return record is not None and record.source == "user"


def _existing_app_ids(catalog_path: Path = DEFAULT_APPS_CATALOG_PATH) -> set[str]:
    service = AppCatalogService(catalog_path)
    return {record.app_id for record in service.get_all_apps()}


def smoke_check(record: AppRecord) -> list[dict[str, Any]]:
    pipeline = CommandPipeline()

    surfaces = [record.display_name, *record.speech_forms]
    surfaces = list(dict.fromkeys([item for item in surfaces if item]))[:5]

    phrases: list[str] = []

    for surface in surfaces:
        phrases.extend(
            [
                f"открой {surface}",
                f"запусти {surface}",
                f"{surface} открой",
            ]
        )

    results = []

    for phrase in phrases[:9]:
        output = pipeline.run(phrase, execute=False, log=False)
        got_skill = output.skill_prediction.skill
        got_app_id = output.args_prediction.args.get("app_id")
        ok = got_skill == "open_app" and got_app_id == record.app_id

        results.append(
            {
                "text": phrase,
                "skill": got_skill,
                "app_id": got_app_id,
                "ok": ok,
            }
        )

    return results


def _run_training(
    progress: ProgressCallback,
    user_apps_path: Path = DEFAULT_APPS_CATALOG_PATH,
    overrides_path: Path = DEFAULT_APP_OVERRIDES_PATH,
) -> list[dict[str, Any]]:
    generated_root = PROJECT_ROOT / "python_agent" / "data" / "user_apps" / "generated"

    open_app_dir = generated_root / "open_app"
    skill_dir = generated_root / "skill_classifier"

    steps = [
        (
            "Генерирую датасет open_app",
            [
                "python_agent.training.generate_open_app_dataset",
                "--output-dir", str(open_app_dir),
                "--apps-catalog-path", str(user_apps_path),
            ],
        ),
        (
            "Обучаю open_app",
            [
                "python_agent.training.train_open_app_arg_model",
                "--data-path", str(open_app_dir / "processed" / "app_train.csv"),
                "--metrics-path", str(open_app_dir / "eval" / "train_metrics.json"),
            ],
        ),
        (
            "Тестирую open_app",
            [
                "python_agent.training.test_open_app_arg_model",
                "--tests-path", str(open_app_dir / "eval" / "manual_tests.jsonl"),
                "--results-path", str(open_app_dir / "eval" / "test_results.json"),
            ],
        ),
        (
            "Генерирую датасет window_control",
            [
                "python_agent.training.generate_window_control_dataset",
                "--user-apps-path", str(user_apps_path),
                "--overrides-path", str(overrides_path),
            ],
        ),
        (
            "Обучаю window_control",
            [
                "python_agent.training.train_window_control_arg_model",
            ],
        ),
        (
            "Тестирую window_control",
            [
                "python_agent.training.test_window_control_arg_model",
            ],
        ),
        (
            "Генерирую датасет window_layout",
            [
                "python_agent.training.generate_window_layout_dataset",
                "--root", str(PROJECT_ROOT),
                "--user-apps-path", str(user_apps_path),
                "--overrides-path", str(overrides_path),
            ],
        ),
        (
            "Обучаю window_layout",
            [
                "python_agent.training.train_window_layout_arg_model",
            ],
        ),
        (
            "Тестирую window_layout",
            [
                "python_agent.training.test_window_layout_arg_model",
            ],
        ),
        (
            "Генерирую датасет skill_classifier",
            [
                "python_agent.training.generate_skill_classifier_dataset",
                "--output-dir", str(skill_dir),
                "--user-apps-path", str(user_apps_path),
                "--overrides-path", str(overrides_path),
            ],
        ),
        (
            "Обучаю skill_classifier",
            [
                "python_agent.training.train_skill_classifier",
                "--data-path", str(skill_dir / "processed" / "skill_train.csv"),
                "--metrics-path", str(skill_dir / "eval" / "train_metrics.json"),
            ],
        ),
        (
            "Тестирую skill_classifier",
            [
                "python_agent.training.test_skill_classifier",
                "--tests-path", str(skill_dir / "eval" / "manual_tests.jsonl"),
                "--results-path", str(skill_dir / "eval" / "test_results.json"),
            ],
        ),
    ]

    results: list[dict[str, Any]] = []

    for message, module in steps:
        progress(message)

        completed = subprocess.run(
            [sys.executable, "-m", *module],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

        result = {
            "step": message,
            "returncode": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
        results.append(result)

        if completed.returncode != 0:
            raise RuntimeError(
                f"{message} failed: {completed.stderr or completed.stdout}"
            )

    return results


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main() -> int:
    _configure_stdio()

    parser = argparse.ArgumentParser(description="Add a user application and retrain app models")
    parser.add_argument("--update", action="store_true", help="Update speech forms for an existing app")
    parser.add_argument("--delete", action="store_true", help="Delete or disable an existing app")
    parser.add_argument("--path", type=Path)
    parser.add_argument("--windows-app-id")
    parser.add_argument("--launch-type", default="apps_folder")
    parser.add_argument("--launch-target")
    parser.add_argument("--display-name", default="")
    parser.add_argument("--app-id")
    parser.add_argument("--speech-form", action="append", default=[])
    parser.add_argument("--no-retrain", action="store_true")
    args = parser.parse_args()

    if args.delete:
        result = delete_user_app(
            DeleteUserAppRequest(
                app_id=args.app_id or "",
                retrain=not args.no_retrain,
            ),
            progress=lambda message: print(message, flush=True),
        )
    elif args.update:
        result = update_user_app(
            UpdateUserAppRequest(
                app_id=args.app_id or "",
                speech_forms=args.speech_form,
                retrain=not args.no_retrain,
            ),
            progress=lambda message: print(message, flush=True),
        )
    else:
        result = add_user_app(
            AddUserAppRequest(
                path=args.path,
                display_name=args.display_name,
                app_id=args.app_id,
                speech_forms=args.speech_form,
                windows_app_id=args.windows_app_id,
                launch_type=args.launch_type,
                launch_target=args.launch_target,
                retrain=not args.no_retrain,
            ),
            progress=lambda message: print(message, flush=True),
        )

    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
