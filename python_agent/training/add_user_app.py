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
from python_agent.resolvers.app_catalog_overrides import (
    AppCatalogOverride,
    DEFAULT_APP_OVERRIDES_PATH,
    disable_app_catalog_entry,
    load_app_catalog_overrides,
    save_app_catalog_overrides,
    update_app_catalog_speech_forms,
)
from python_agent.resolvers.user_app_catalog import (
    DEFAULT_USER_APPS_PATH,
    UserAppRecord,
    add_user_app_record,
    build_user_app_record,
    build_windows_user_app_record,
    delete_user_app_record,
    load_user_apps,
    normalize_app_id,
    normalize_speech_forms,
    save_user_apps,
    update_user_app_speech_forms,
)
from python_agent.resolvers.windows_app_discovery import discover_windows_apps
from python_agent.training.generate_open_app_dataset import APP_CATALOG


PROJECT_ROOT = Path(__file__).resolve().parents[2]

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
    catalog_path: Path = DEFAULT_USER_APPS_PATH
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
    catalog_path: Path = DEFAULT_USER_APPS_PATH
    index_output_path: Path = app_indexer.DEFAULT_OUTPUT_PATH
    overrides_path: Path = DEFAULT_APP_OVERRIDES_PATH


@dataclass(frozen=True)
class DeleteUserAppRequest:
    app_id: str
    retrain: bool = True
    catalog_path: Path = DEFAULT_USER_APPS_PATH
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
    catalog_path: Path = DEFAULT_USER_APPS_PATH
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

    existing_app_ids = _existing_app_ids(request.catalog_path, request.overrides_path)
    progress("Сохраняю приложение")
    add_user_app_record(record, request.catalog_path, existing_app_ids=existing_app_ids)

    progress("Обновляю индекс")
    index_summary = rebuild_apps_index(request.catalog_path, request.index_output_path, request.overrides_path)

    commands: list[dict[str, Any]] = []
    smoke_results: list[dict[str, Any]] = []
    if request.retrain:
        commands.extend(_run_training(progress, request.catalog_path, request.overrides_path))

        progress("Проверяю новые фразы")
        smoke_results = smoke_check(record)
        failed_smoke = [item for item in smoke_results if not item["ok"]]
        if failed_smoke:
            raise RuntimeError("New app smoke checks failed: " + json.dumps(failed_smoke, ensure_ascii=False))

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

    user_records = {record.app_id: record for record in load_user_apps(request.catalog_path)}
    overrides = dict(load_app_catalog_overrides(request.overrides_path))
    applied: list[dict[str, Any]] = []
    smoke_records: list[UserAppRecord] = []

    if not request.changes:
        raise ValueError("No app catalog changes to apply")

    for raw_change in request.changes:
        operation = raw_change.operation.strip().lower()
        app_id = normalize_app_id(raw_change.app_id)
        if operation not in {"add", "update_speech_forms", "delete"}:
            raise ValueError(f"Unsupported app catalog operation: {raw_change.operation}")
        if not app_id:
            raise ValueError("app_id is required")

        if operation == "add":
            record = _build_record(
                AddUserAppRequest(
                    path=raw_change.path,
                    display_name=raw_change.display_name,
                    app_id=app_id,
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
            active_builtin_ids = {
                builtin_id
                for builtin_id in APP_CATALOG
                if not (builtin_id in overrides and overrides[builtin_id].disabled)
            }
            if record.app_id in user_records or record.app_id in active_builtin_ids:
                raise ValueError(f"app_id is already used: {record.app_id}")

            user_records[record.app_id] = record
            applied.append({"operation": "add", "source": "user", "app_id": record.app_id})
            smoke_records.append(record)
            continue

        if operation == "update_speech_forms":
            forms = normalize_speech_forms(raw_change.speech_forms)
            if app_id in user_records:
                current = user_records[app_id]
                record = UserAppRecord(
                    app_id=current.app_id,
                    display_name=current.display_name,
                    launch_type=current.launch_type,
                    launch_target=current.launch_target,
                    target_path=current.target_path,
                    working_directory=current.working_directory,
                    speech_forms=forms,
                )
                user_records[app_id] = record
                applied.append({"operation": "update_speech_forms", "source": "user", "app_id": app_id})
                smoke_records.append(record)
            elif app_id in APP_CATALOG:
                current = overrides.get(app_id, AppCatalogOverride(app_id=app_id))
                overrides[app_id] = AppCatalogOverride(
                    app_id=app_id,
                    speech_forms=forms,
                    disabled=current.disabled,
                )
                record = _builtin_record_payload(app_id, forms, disabled=current.disabled)
                applied.append({"operation": "update_speech_forms", "source": "builtin", "app_id": app_id})
                if not current.disabled:
                    smoke_records.append(record)
            else:
                raise ValueError(f"app not found: {app_id}")
            continue

        if operation == "delete":
            if app_id in user_records:
                del user_records[app_id]
                applied.append({"operation": "delete", "source": "user", "app_id": app_id})
            elif app_id in APP_CATALOG:
                current = overrides.get(app_id, AppCatalogOverride(app_id=app_id))
                overrides[app_id] = AppCatalogOverride(
                    app_id=app_id,
                    speech_forms=current.speech_forms,
                    disabled=True,
                )
                applied.append({"operation": "delete", "source": "builtin", "app_id": app_id})
            else:
                raise ValueError(f"app not found: {app_id}")

    progress("Сохраняю изменения")
    save_user_apps(sorted(user_records.values(), key=lambda item: item.app_id), request.catalog_path)
    save_app_catalog_overrides(overrides, request.overrides_path)

    progress("Обновляю индекс")
    index_summary = rebuild_apps_index(request.catalog_path, request.index_output_path, request.overrides_path)

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
            raise RuntimeError("App catalog smoke checks failed: " + json.dumps(failed_smoke, ensure_ascii=False))

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

    progress("Удаляю приложение")
    if _is_user_app(request.app_id, request.catalog_path):
        record: Any = delete_user_app_record(request.app_id, request.catalog_path)
    elif request.app_id in APP_CATALOG:
        override = disable_app_catalog_entry(request.app_id, request.overrides_path)
        record = _builtin_record_payload(request.app_id, override.speech_forms, disabled=True)
    else:
        raise ValueError(f"app not found: {request.app_id}")

    progress("Обновляю индекс")
    index_summary = rebuild_apps_index(request.catalog_path, request.index_output_path, request.overrides_path)

    commands: list[dict[str, Any]] = []
    if request.retrain:
        commands.extend(_run_training(progress, request.catalog_path, request.overrides_path))

    progress("Готово")
    return AddUserAppResult(
        app=record,
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
    if _is_user_app(request.app_id, request.catalog_path):
        record: Any = update_user_app_speech_forms(
            request.app_id,
            request.speech_forms,
            request.catalog_path,
        )
    elif request.app_id in APP_CATALOG:
        override = update_app_catalog_speech_forms(
            request.app_id,
            request.speech_forms,
            request.overrides_path,
        )
        record = _builtin_record_payload(request.app_id, override.speech_forms, disabled=override.disabled)
    else:
        raise ValueError(f"app not found: {request.app_id}")

    progress("Обновляю индекс")
    index_summary = rebuild_apps_index(request.catalog_path, request.index_output_path, request.overrides_path)

    commands: list[dict[str, Any]] = []
    smoke_results: list[dict[str, Any]] = []
    if request.retrain:
        commands.extend(_run_training(progress, request.catalog_path, request.overrides_path))

        progress("Проверяю новые фразы")
        smoke_results = smoke_check(record)
        failed_smoke = [item for item in smoke_results if not item["ok"]]
        if failed_smoke:
            raise RuntimeError("Updated app smoke checks failed: " + json.dumps(failed_smoke, ensure_ascii=False))

    progress("Готово")
    return AddUserAppResult(
        app=record,
        index_summary=index_summary,
        commands=commands,
        smoke_results=smoke_results,
    )


def _build_record(request: AddUserAppRequest) -> UserAppRecord:
    if request.windows_app_id:
        return build_windows_user_app_record(
            windows_app_id=request.windows_app_id,
            display_name=request.display_name,
            launch_type=request.launch_type,
            launch_target=request.launch_target,
            app_id=request.app_id,
            speech_forms=request.speech_forms,
        )

    if request.path is None:
        raise ValueError("Application path or Windows app id is required")

    app_path = request.path.expanduser()
    if not app_path.exists() or not app_path.is_file():
        raise ValueError(f"Application path does not exist: {app_path}")
    if app_path.suffix.lower() != ".exe":
        raise ValueError("Only .exe applications are supported for this flow")

    return build_user_app_record(
        path=app_path,
        display_name=request.display_name,
        app_id=request.app_id,
        speech_forms=request.speech_forms,
    )


def rebuild_apps_index(
    user_catalog_path: Path = DEFAULT_USER_APPS_PATH,
    output_path: Path = app_indexer.DEFAULT_OUTPUT_PATH,
    overrides_path: Path = DEFAULT_APP_OVERRIDES_PATH,
) -> dict[str, Any]:
    index = app_indexer.build_index(app_indexer.DEFAULT_MANUAL_CONFIG, user_catalog_path, overrides_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return dict(index["summary"])


def list_windows_apps() -> list[dict[str, str]]:
    return [entry.to_dict() for entry in discover_windows_apps()]


def list_user_app_records(catalog_path: Path = DEFAULT_USER_APPS_PATH) -> list[dict[str, Any]]:
    return [record.to_dict() for record in load_user_apps(catalog_path)]


def _is_user_app(app_id: str, catalog_path: Path = DEFAULT_USER_APPS_PATH) -> bool:
    normalized_app_id = normalize_app_id(app_id)
    return any(record.app_id == normalized_app_id for record in load_user_apps(catalog_path))


def _builtin_record_payload(app_id: str, speech_forms: list[str], disabled: bool = False) -> UserAppRecord:
    entry = APP_CATALOG.get(app_id, {})
    forms = entry.get("surface_forms", []) if isinstance(entry, dict) else []
    display_name = str(forms[0]) if forms else app_id
    return UserAppRecord(
        app_id=app_id,
        display_name=display_name,
        launch_type="builtin",
        launch_target=app_id,
        target_path=app_id,
        working_directory="",
        speech_forms=speech_forms,
    )


def smoke_check(record: UserAppRecord) -> list[dict[str, Any]]:
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


def _existing_app_ids(_user_catalog_path: Path, overrides_path: Path = DEFAULT_APP_OVERRIDES_PATH) -> set[str]:
    overrides = load_app_catalog_overrides(overrides_path)
    return {
        app_id
        for app_id in APP_CATALOG
        if not (app_id in overrides and overrides[app_id].disabled)
    }


def _run_training(
    progress: ProgressCallback,
    user_apps_path: Path = DEFAULT_USER_APPS_PATH,
    overrides_path: Path = DEFAULT_APP_OVERRIDES_PATH,
) -> list[dict[str, Any]]:
    generated_root = PROJECT_ROOT / "python_agent" / "data" / "user_apps" / "generated"

    open_app_dir = generated_root / "open_app"
    skill_dir = generated_root / "skill_classifier"

    steps = [
        # 1. open_app: учим распознавать новое приложение как app_id
        (
            "Генерирую датасет open_app",
            [
                "python_agent.training.generate_open_app_dataset",
                "--output-dir", str(open_app_dir),
                "--user-apps-path", str(user_apps_path),
                "--overrides-path", str(overrides_path),
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

        # 2. window_control: ВАЖНО
        # Раньше этого блока не было, поэтому close/minimize/maximize/restore
        # не узнавали новые приложения.
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

        # 3. window_layout: раскладка окон тоже должна быть свежей
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

        # 4. skill_classifier должен идти ПОСЛЕДНИМ
        # потому что его генератор берёт данные из window_control/window_layout.
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
    parser.add_argument("--update", action="store_true", help="Update speech forms for an existing user app")
    parser.add_argument("--delete", action="store_true", help="Delete an existing user app")
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
