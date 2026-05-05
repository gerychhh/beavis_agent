from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from python_agent.api.result import ok, fail
from python_agent.training.add_user_app import (
    AddUserAppRequest,
    UpdateUserAppRequest,
    DeleteUserAppRequest,
    ApplyUserAppChangesRequest,
    AppCatalogChange,
    add_user_app,
    update_user_app,
    delete_user_app,
    apply_user_app_changes,
    list_windows_apps,
    list_user_app_records,
)


ProgressCallback = Callable[[str], None]


class AppsApi:
    """
    Stable API for app catalog management.

    This wraps the existing app/user-app functions. Later these functions can
    be moved from training/add_user_app.py into services/app_service.py without
    changing the UI contract.
    """

    def list_windows_apps(self) -> dict[str, Any]:
        try:
            return ok(list_windows_apps())
        except Exception as error:
            return fail(error, code="LIST_WINDOWS_APPS_ERROR")

    def list_user_apps(self) -> dict[str, Any]:
        try:
            return ok(list_user_app_records())
        except Exception as error:
            return fail(error, code="LIST_USER_APPS_ERROR")

    def add(
        self,
        display_name: str,
        path: str = "",
        app_id: str = "",
        speech_forms: list[str] | None = None,
        windows_app_id: str = "",
        launch_type: str = "apps_folder",
        launch_target: str = "",
        retrain: bool = True,
        progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        try:
            result = add_user_app(
                AddUserAppRequest(
                    display_name=display_name,
                    path=Path(path) if path else None,
                    app_id=app_id or None,
                    speech_forms=speech_forms or [],
                    windows_app_id=windows_app_id or None,
                    launch_type=launch_type,
                    launch_target=launch_target or None,
                    retrain=retrain,
                ),
                progress=progress,
            )
            return ok(result.to_dict())
        except Exception as error:
            return fail(error, code="ADD_APP_ERROR")

    def update_speech_forms(
        self,
        app_id: str,
        speech_forms: list[str],
        retrain: bool = True,
        progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        try:
            result = update_user_app(
                UpdateUserAppRequest(
                    app_id=app_id,
                    speech_forms=speech_forms,
                    retrain=retrain,
                ),
                progress=progress,
            )
            return ok(result.to_dict())
        except Exception as error:
            return fail(error, code="UPDATE_APP_ERROR")

    def delete(
        self,
        app_id: str,
        retrain: bool = True,
        progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        try:
            result = delete_user_app(
                DeleteUserAppRequest(
                    app_id=app_id,
                    retrain=retrain,
                ),
                progress=progress,
            )
            return ok(result.to_dict())
        except Exception as error:
            return fail(error, code="DELETE_APP_ERROR")

    def apply_changes(
        self,
        changes: list[dict[str, Any]],
        retrain: bool = True,
        progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        try:
            request_changes: list[AppCatalogChange] = []

            for item in changes:
                path_value = str(item.get("path") or "").strip()

                request_changes.append(
                    AppCatalogChange(
                        operation=str(item.get("operation") or ""),
                        source=str(item.get("source") or ""),
                        app_id=str(item.get("app_id") or ""),
                        display_name=str(item.get("display_name") or ""),
                        speech_forms=[
                            str(value)
                            for value in item.get("speech_forms") or []
                        ],
                        path=Path(path_value) if path_value else None,
                        windows_app_id=str(item.get("windows_app_id") or "") or None,
                        launch_type=str(item.get("launch_type") or "apps_folder"),
                        launch_target=str(item.get("launch_target") or "") or None,
                    )
                )

            result = apply_user_app_changes(
                ApplyUserAppChangesRequest(
                    changes=request_changes,
                    retrain=retrain,
                ),
                progress=progress,
            )
            return ok(result.to_dict())
        except Exception as error:
            return fail(error, code="APPLY_APP_CHANGES_ERROR")
