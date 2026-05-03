from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from python_agent.resolvers.user_app_catalog import load_user_apps
from python_agent.resolvers.app_catalog_overrides import load_app_catalog_overrides
from python_agent.resolvers.windows_app_discovery import make_entry
from python_agent.resolvers import app_indexer
from python_agent.training import generate_open_app_dataset, generate_skill_classifier_dataset, generate_window_control_dataset
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


def main() -> int:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        app_path = root / "UnitTool.exe"
        catalog_path = root / "apps.json"
        overrides_path = root / "catalog_overrides.json"
        index_path = root / "apps_index.json"
        app_path.write_text("placeholder", encoding="utf-8")

        result = add_user_app(
            AddUserAppRequest(
                path=app_path,
                display_name="Unit Tool",
                app_id="unit_tool",
                speech_forms=["юнит тул", "тестовая тулза"],
                retrain=False,
                catalog_path=catalog_path,
                index_output_path=index_path,
                overrides_path=overrides_path,
            )
        )

        apps = load_user_apps(catalog_path)
        index = json.loads(index_path.read_text(encoding="utf-8"))
        records = [
            item for item in index["records"]
            if item.get("app_id") == "unit_tool"
        ]

        checks = {
            "result_app_id": result.app.app_id == "unit_tool",
            "catalog_written": len(apps) == 1 and apps[0].speech_forms == ["unit tool", "unittool", "юнит тул", "тестовая тулза"],
            "index_written": len(records) == 1 and records[0].get("source") == "user",
            "open_app_generator_reads_user": "unit_tool" in generate_open_app_dataset.build_app_catalog(catalog_path, overrides_path),
            "skill_generator_reads_user": "unit_tool" in generate_skill_classifier_dataset.build_app_catalog(catalog_path, overrides_path),
        }

        windows_result = add_user_app(
            AddUserAppRequest(
                display_name="Windows Unit App",
                app_id="windows_unit_app",
                windows_app_id="Vendor.WindowsUnit_123!App",
                speech_forms=["вин юнит"],
                retrain=False,
                catalog_path=catalog_path,
                index_output_path=index_path,
                overrides_path=overrides_path,
            )
        )
        apps = load_user_apps(catalog_path)
        index = json.loads(index_path.read_text(encoding="utf-8"))
        windows_records = [
            item for item in index["records"]
            if item.get("app_id") == "windows_unit_app"
        ]
        checks.update({
            "windows_result_app_id": windows_result.app.app_id == "windows_unit_app",
            "windows_catalog_written": any(
                item.app_id == "windows_unit_app"
                and item.launch_type == "apps_folder"
                and item.launch_target == r"shell:AppsFolder\Vendor.WindowsUnit_123!App"
                for item in apps
            ),
            "windows_index_written": len(windows_records) == 1 and windows_records[0].get("exists") is True,
            "windows_discovery_entry": make_entry("Windows Unit App", "Vendor.WindowsUnit_123!App", "start_apps") is not None,
            "windows_discovery_filters_url": make_entry("Help", "https://example.com", "apps_folder") is None,
        })

        update_result = update_user_app(
            UpdateUserAppRequest(
                app_id="unit_tool",
                speech_forms=["новый сленг", "unit alias"],
                retrain=False,
                catalog_path=catalog_path,
                index_output_path=index_path,
                overrides_path=overrides_path,
            )
        )
        apps = load_user_apps(catalog_path)
        checks.update({
            "update_result_app_id": update_result.app.app_id == "unit_tool",
            "speech_forms_updated": any(
                item.app_id == "unit_tool"
                and item.speech_forms == ["новый сленг", "unit alias"]
                for item in apps
            ),
        })

        delete_result = delete_user_app(
            DeleteUserAppRequest(
                app_id="windows_unit_app",
                retrain=False,
                catalog_path=catalog_path,
                index_output_path=index_path,
                overrides_path=overrides_path,
            )
        )
        apps = load_user_apps(catalog_path)
        index = json.loads(index_path.read_text(encoding="utf-8"))
        checks.update({
            "delete_result_app_id": delete_result.app.app_id == "windows_unit_app",
            "deleted_from_catalog": all(item.app_id != "windows_unit_app" for item in apps),
            "deleted_from_index": all(
                item.get("app_id") != "windows_unit_app"
                for item in index.get("records", [])
                if item.get("source") == "user"
            ),
        })

        index_only_ids = [
            str(item.get("app_id"))
            for item in app_indexer.build_index(app_indexer.DEFAULT_MANUAL_CONFIG, catalog_path).get("records", [])
            if item.get("app_id") and item.get("app_id") not in generate_open_app_dataset.APP_CATALOG
        ]
        if index_only_ids:
            reusable_app_id = index_only_ids[0]
            reusable_result = add_user_app(
                AddUserAppRequest(
                    path=app_path,
                    display_name="Reusable Index Id",
                    app_id=reusable_app_id,
                    retrain=False,
                    catalog_path=catalog_path,
                    index_output_path=index_path,
                    overrides_path=overrides_path,
                )
            )
            checks["index_only_app_id_is_reusable"] = reusable_result.app.app_id == reusable_app_id
        else:
            checks["index_only_app_id_is_reusable"] = True

        try:
            add_user_app(
                AddUserAppRequest(
                    path=app_path,
                    display_name="Unit Tool Copy",
                    app_id="unit_tool",
                    retrain=False,
                    catalog_path=catalog_path,
                    index_output_path=index_path,
                    overrides_path=overrides_path,
                )
            )
            checks["duplicate_rejected"] = False
        except ValueError:
            checks["duplicate_rejected"] = True

        builtin_update = update_user_app(
            UpdateUserAppRequest(
                app_id="chrome",
                speech_forms=["мой браузер"],
                retrain=False,
                catalog_path=catalog_path,
                index_output_path=index_path,
                overrides_path=overrides_path,
            )
        )
        open_catalog = generate_open_app_dataset.build_app_catalog(catalog_path, overrides_path)
        skill_catalog = generate_skill_classifier_dataset.build_app_catalog(catalog_path, overrides_path)
        overrides = load_app_catalog_overrides(overrides_path)
        checks.update({
            "builtin_update_result_app_id": builtin_update.app.app_id == "chrome",
            "builtin_override_written": overrides.get("chrome") is not None and overrides["chrome"].speech_forms == ["мой браузер"],
            "builtin_override_in_open_app_dataset": "мой браузер" in open_catalog["chrome"]["surface_forms"],
            "builtin_override_in_skill_dataset": "мой браузер" in skill_catalog["chrome"],
        })

        builtin_delete = delete_user_app(
            DeleteUserAppRequest(
                app_id="chrome",
                retrain=False,
                catalog_path=catalog_path,
                index_output_path=index_path,
                overrides_path=overrides_path,
            )
        )
        open_catalog = generate_open_app_dataset.build_app_catalog(catalog_path, overrides_path)
        disabled_open_catalog = generate_open_app_dataset.build_disabled_app_catalog(overrides_path, catalog_path)
        open_rows, _combined = generate_open_app_dataset.generate_dataset(
            samples_per_app=4,
            unknown_samples=4,
            seed=1,
            catalog=open_catalog,
            disabled_catalog=disabled_open_catalog,
        )
        skill_catalog = generate_skill_classifier_dataset.build_app_catalog(catalog_path, overrides_path)
        disabled_skill_catalog = generate_skill_classifier_dataset.build_disabled_app_catalog(overrides_path, catalog_path)
        disabled_skill_rows = generate_skill_classifier_dataset.generate_disabled_open_app_unknown_rows(
            generate_skill_classifier_dataset.random.Random(1),
            disabled_skill_catalog,
        )
        window_control_catalog = generate_window_control_dataset.build_apps(catalog_path, overrides_path)
        overrides = load_app_catalog_overrides(overrides_path)
        checks.update({
            "builtin_delete_result_app_id": builtin_delete.app.app_id == "chrome",
            "builtin_disabled_written": overrides.get("chrome") is not None and overrides["chrome"].disabled is True,
            "builtin_removed_from_open_app_dataset": "chrome" not in open_catalog,
            "builtin_deleted_open_app_negatives": any(
                row["app_id"] == "unknown" and "хром" in row["text"]
                for row in open_rows
            ),
            "builtin_removed_from_skill_dataset": "chrome" not in skill_catalog,
            "builtin_deleted_skill_routes_open_app": any(
                label == generate_skill_classifier_dataset.SKILL_OPEN_APP and "хром" in text
                for text, label in disabled_skill_rows
            ),
            "builtin_removed_from_window_control_dataset": "chrome" not in window_control_catalog,
        })

        reused_builtin_id = add_user_app(
            AddUserAppRequest(
                path=app_path,
                display_name="Custom Chrome Replacement",
                app_id="chrome",
                speech_forms=["мой новый хром"],
                retrain=False,
                catalog_path=catalog_path,
                index_output_path=index_path,
                overrides_path=overrides_path,
            )
        )
        open_catalog = generate_open_app_dataset.build_app_catalog(catalog_path, overrides_path)
        disabled_open_catalog = generate_open_app_dataset.build_disabled_app_catalog(overrides_path, catalog_path)
        window_control_catalog = generate_window_control_dataset.build_apps(catalog_path, overrides_path)
        checks.update({
            "disabled_builtin_id_is_reusable": reused_builtin_id.app.app_id == "chrome",
            "reused_builtin_id_is_active_user_dataset": "мой новый хром" in open_catalog["chrome"]["surface_forms"],
            "reused_builtin_id_removes_disabled_negatives": "chrome" not in disabled_open_catalog,
            "reused_builtin_id_is_active_window_control_dataset": "мой новый хром" in window_control_catalog["chrome"],
        })

        batch_catalog_path = root / "batch_apps.json"
        batch_overrides_path = root / "batch_catalog_overrides.json"
        batch_index_path = root / "batch_apps_index.json"
        batch_app_path = root / "BatchTool.exe"
        batch_app_path.write_text("placeholder", encoding="utf-8")
        batch_result = apply_user_app_changes(
            ApplyUserAppChangesRequest(
                changes=[
                    AppCatalogChange(
                        operation="delete",
                        source="builtin",
                        app_id="edge",
                    ),
                    AppCatalogChange(
                        operation="add",
                        source="user",
                        app_id="edge",
                        display_name="Custom Edge",
                        path=batch_app_path,
                        launch_type="exe",
                        speech_forms=["кастомный эдж"],
                    ),
                    AppCatalogChange(
                        operation="update_speech_forms",
                        source="builtin",
                        app_id="firefox",
                        speech_forms=["мой фаер"],
                    ),
                ],
                retrain=False,
                catalog_path=batch_catalog_path,
                index_output_path=batch_index_path,
                overrides_path=batch_overrides_path,
            )
        )
        batch_apps = load_user_apps(batch_catalog_path)
        batch_overrides = load_app_catalog_overrides(batch_overrides_path)
        batch_open_catalog = generate_open_app_dataset.build_app_catalog(batch_catalog_path, batch_overrides_path)
        batch_disabled_open_catalog = generate_open_app_dataset.build_disabled_app_catalog(batch_overrides_path, batch_catalog_path)
        checks.update({
            "batch_result_count": len(batch_result.changes) == 3,
            "batch_add_written": any(item.app_id == "edge" and "кастомный эдж" in item.speech_forms for item in batch_apps),
            "batch_delete_builtin_written": batch_overrides.get("edge") is not None and batch_overrides["edge"].disabled is True,
            "batch_reused_disabled_builtin_id_active": "кастомный эдж" in batch_open_catalog["edge"]["surface_forms"],
            "batch_reused_disabled_builtin_id_not_negative": "edge" not in batch_disabled_open_catalog,
            "batch_builtin_update_written": batch_overrides.get("firefox") is not None and batch_overrides["firefox"].speech_forms == ["мой фаер"],
            "batch_builtin_update_in_dataset": "мой фаер" in batch_open_catalog["firefox"]["surface_forms"],
        })

        try:
            apply_user_app_changes(
                ApplyUserAppChangesRequest(
                    changes=[
                        AppCatalogChange(
                            operation="add",
                            source="user",
                            app_id="chrome",
                            display_name="Duplicate Chrome",
                            path=batch_app_path,
                        ),
                    ],
                    retrain=False,
                    catalog_path=root / "batch_conflict_apps.json",
                    index_output_path=root / "batch_conflict_index.json",
                    overrides_path=root / "batch_conflict_overrides.json",
                )
            )
            checks["batch_conflict_rejected"] = False
        except ValueError:
            checks["batch_conflict_rejected"] = True

        failed = [name for name, ok in checks.items() if not ok]
        print(json.dumps({
            "checks": checks,
            "failed": failed,
        }, ensure_ascii=False, indent=2))
        return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
