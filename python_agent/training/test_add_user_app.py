from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from python_agent.resolvers.app_catalog_service import AppCatalogService, AppRecord
from python_agent.training import (
    generate_open_app_dataset,
    generate_skill_classifier_dataset,
    generate_window_control_dataset,
)
from python_agent.training.add_user_app import (
    AddUserAppRequest,
    AppCatalogChange,
    ApplyUserAppChangesRequest,
    DeleteUserAppRequest,
    UpdateUserAppRequest,
    add_user_app,
    apply_user_app_changes,
    delete_user_app,
    update_user_app,
)


def seed_catalog(catalog_path: Path) -> None:
    AppCatalogService(catalog_path).save([
        AppRecord(
            app_id="notepad",
            display_name="Notepad",
            source="builtin",
            enabled=True,
            launch_type="builtin",
            speech_forms=["notepad", "notes"],
            priority=100,
        ),
        AppRecord(
            app_id="edge",
            display_name="Edge",
            source="builtin",
            enabled=True,
            launch_type="builtin",
            speech_forms=["edge"],
            priority=100,
        ),
        AppRecord(
            app_id="firefox",
            display_name="Firefox",
            source="builtin",
            enabled=True,
            launch_type="builtin",
            speech_forms=["firefox"],
            priority=100,
        ),
    ])


def read_index(index_path: Path) -> dict:
    return json.loads(index_path.read_text(encoding="utf-8"))


def catalog_forms(catalog: dict, app_id: str) -> list[str]:
    forms = catalog.get(app_id, [])
    return forms if isinstance(forms, list) else []


def main() -> int:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        app_path = root / "UnitTool.exe"
        app_path.write_text("placeholder", encoding="utf-8")

        catalog_path = root / "apps_catalog.json"
        index_path = root / "apps_index.json"
        seed_catalog(catalog_path)

        checks: dict[str, bool] = {}

        result = add_user_app(
            AddUserAppRequest(
                path=app_path,
                display_name="Unit Tool",
                app_id="unit_tool",
                speech_forms=["unit tool", "unit alias"],
                retrain=False,
                catalog_path=catalog_path,
                index_output_path=index_path,
            )
        )
        apps = AppCatalogService(catalog_path).get_all_apps()
        index = read_index(index_path)
        unit_index_records = [
            item for item in index["records"] if item.get("app_id") == "unit_tool"
        ]
        open_catalog = generate_open_app_dataset.build_app_catalog(catalog_path)
        skill_catalog = generate_skill_classifier_dataset.build_app_catalog(catalog_path)
        control_catalog = generate_window_control_dataset.build_apps(catalog_path)
        checks.update({
            "add_result_app_id": result.app.app_id == "unit_tool",
            "add_catalog_written": any(
                app.app_id == "unit_tool" and "unit alias" in app.speech_forms
                for app in apps
            ),
            "runtime_index_written": len(unit_index_records) == 1
            and unit_index_records[0].get("source") == "user"
            and unit_index_records[0].get("exists") is True,
            "open_app_dataset_reads_catalog": "unit_tool" in open_catalog,
            "skill_dataset_reads_catalog": "unit_tool" in skill_catalog,
            "window_control_dataset_reads_catalog": "unit_tool" in control_catalog,
        })

        windows_result = add_user_app(
            AddUserAppRequest(
                display_name="Windows Unit App",
                app_id="windows_unit_app",
                windows_app_id="Vendor.WindowsUnit_123!App",
                speech_forms=["windows unit"],
                retrain=False,
                catalog_path=catalog_path,
                index_output_path=index_path,
            )
        )
        windows_app = AppCatalogService(catalog_path).get_app("windows_unit_app")
        windows_index_records = [
            item
            for item in read_index(index_path)["records"]
            if item.get("app_id") == "windows_unit_app"
        ]
        checks.update({
            "windows_result_app_id": windows_result.app.app_id == "windows_unit_app",
            "windows_shell_target_written": windows_app is not None
            and windows_app.launch_type == "apps_folder"
            and windows_app.launch_target == r"shell:AppsFolder\Vendor.WindowsUnit_123!App",
            "windows_runtime_index_written": len(windows_index_records) == 1
            and windows_index_records[0].get("exists") is True,
        })

        update_result = update_user_app(
            UpdateUserAppRequest(
                app_id="unit_tool",
                speech_forms=["updated alias", "unit alias"],
                retrain=False,
                catalog_path=catalog_path,
                index_output_path=index_path,
            )
        )
        updated_app = AppCatalogService(catalog_path).get_app("unit_tool")
        checks.update({
            "update_result_app_id": update_result.app.app_id == "unit_tool",
            "speech_forms_updated": updated_app is not None
            and "updated alias" in updated_app.speech_forms,
        })

        delete_result = delete_user_app(
            DeleteUserAppRequest(
                app_id="windows_unit_app",
                retrain=False,
                catalog_path=catalog_path,
                index_output_path=index_path,
            )
        )
        checks.update({
            "delete_result_app_id": delete_result.app.app_id == "windows_unit_app",
            "user_app_deleted_from_catalog": AppCatalogService(catalog_path).get_app("windows_unit_app") is None,
            "user_app_deleted_from_index": all(
                item.get("app_id") != "windows_unit_app"
                for item in read_index(index_path).get("records", [])
            ),
        })

        try:
            add_user_app(
                AddUserAppRequest(
                    path=app_path,
                    display_name="Unit Tool Copy",
                    app_id="unit_tool",
                    retrain=False,
                    catalog_path=catalog_path,
                    index_output_path=index_path,
                )
            )
            checks["duplicate_user_rejected"] = False
        except ValueError:
            checks["duplicate_user_rejected"] = True

        builtin_update = update_user_app(
            UpdateUserAppRequest(
                app_id="notepad",
                speech_forms=["my notes"],
                retrain=False,
                catalog_path=catalog_path,
                index_output_path=index_path,
            )
        )
        open_catalog = generate_open_app_dataset.build_app_catalog(catalog_path)
        skill_catalog = generate_skill_classifier_dataset.build_app_catalog(catalog_path)
        checks.update({
            "builtin_update_result_app_id": builtin_update.app.app_id == "notepad",
            "builtin_update_in_open_dataset": "my notes"
            in catalog_forms(open_catalog, "notepad"),
            "builtin_update_in_skill_dataset": "my notes" in skill_catalog["notepad"],
        })

        builtin_delete = delete_user_app(
            DeleteUserAppRequest(
                app_id="notepad",
                retrain=False,
                catalog_path=catalog_path,
                index_output_path=index_path,
            )
        )
        checks.update({
            "builtin_delete_result_app_id": builtin_delete.app.app_id == "notepad",
            "builtin_is_disabled": AppCatalogService(catalog_path).get_app("notepad") is not None
            and AppCatalogService(catalog_path).get_app("notepad").enabled is False,
            "builtin_removed_from_open_dataset": "notepad"
            not in generate_open_app_dataset.build_app_catalog(catalog_path),
            "builtin_removed_from_window_control_dataset": "notepad"
            not in generate_window_control_dataset.build_apps(catalog_path),
        })

        replacement = add_user_app(
            AddUserAppRequest(
                path=app_path,
                display_name="Custom Notepad",
                app_id="notepad",
                speech_forms=["custom notepad"],
                retrain=False,
                catalog_path=catalog_path,
                index_output_path=index_path,
            )
        )
        replacement_app = AppCatalogService(catalog_path).get_app("notepad")
        checks.update({
            "disabled_builtin_id_reused": replacement.app.app_id == "notepad",
            "replacement_is_user_app": replacement_app is not None
            and replacement_app.source == "user"
            and replacement_app.enabled is True,
            "replacement_runtime_index_written": any(
                item.get("app_id") == "notepad" and item.get("source") == "user"
                for item in read_index(index_path).get("records", [])
            ),
        })

        batch_catalog_path = root / "batch_catalog.json"
        batch_index_path = root / "batch_index.json"
        seed_catalog(batch_catalog_path)
        batch_result = apply_user_app_changes(
            ApplyUserAppChangesRequest(
                changes=[
                    AppCatalogChange(operation="delete", source="builtin", app_id="edge"),
                    AppCatalogChange(
                        operation="add",
                        source="user",
                        app_id="edge",
                        display_name="Custom Edge",
                        path=app_path,
                        launch_type="exe",
                        speech_forms=["custom edge"],
                    ),
                    AppCatalogChange(
                        operation="update_speech_forms",
                        source="builtin",
                        app_id="notepad",
                        speech_forms=["my notepad"],
                    ),
                ],
                retrain=False,
                catalog_path=batch_catalog_path,
                index_output_path=batch_index_path,
            )
        )
        batch_service = AppCatalogService(batch_catalog_path)
        batch_open_catalog = generate_open_app_dataset.build_app_catalog(batch_catalog_path)
        checks.update({
            "batch_result_count": len(batch_result.changes) == 3,
            "batch_replaces_disabled_builtin_id": batch_service.get_app("edge") is not None
            and batch_service.get_app("edge").source == "user",
            "batch_replacement_in_dataset": "custom edge"
            in catalog_forms(batch_open_catalog, "edge"),
            "batch_builtin_update_in_dataset": "my notepad"
            in catalog_forms(batch_open_catalog, "notepad"),
        })

        conflict_catalog_path = root / "conflict_catalog.json"
        seed_catalog(conflict_catalog_path)
        try:
            apply_user_app_changes(
                ApplyUserAppChangesRequest(
                    changes=[
                        AppCatalogChange(
                            operation="add",
                            source="user",
                            app_id="edge",
                            display_name="Duplicate Edge",
                            path=app_path,
                            launch_type="exe",
                        ),
                    ],
                    retrain=False,
                    catalog_path=conflict_catalog_path,
                    index_output_path=root / "conflict_index.json",
                )
            )
            checks["batch_enabled_builtin_conflict_rejected"] = False
        except ValueError:
            checks["batch_enabled_builtin_conflict_rejected"] = True

        failed = [name for name, passed in checks.items() if not passed]
        print(json.dumps({"checks": checks, "failed": failed}, ensure_ascii=False, indent=2))
        return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
