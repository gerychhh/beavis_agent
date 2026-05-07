from __future__ import annotations

import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from python_agent.api.result import ok, fail
from python_agent.training.add_user_app import (
    AddUserAppRequest,
    UpdateUserAppRequest,
    DeleteUserAppRequest,
    ApplyUserAppChangesRequest,
    SyncVisibleAppsRequest,
    AppCatalogChange,
    add_user_app,
    update_user_app,
    delete_user_app,
    apply_user_app_changes,
    sync_visible_user_apps,
    retrain_apps_pipeline,
    TrainingCancelled,
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

    def __init__(self) -> None:
        self._training_lock = threading.Lock()
        self._training_run_lock = threading.Lock()
        self._training_job: dict[str, Any] | None = None

    def _training_snapshot(self) -> dict[str, Any]:
        with self._training_lock:
            return dict(self._training_job or {"running": False, "status": "idle"})

    def retrain_start(self) -> dict[str, Any]:
        try:
            with self._training_lock:
                if self._training_job and self._training_job.get("running"):
                    self._training_job["cancel_requested"] = True
                    self._training_job["last_message"] = "Cancelling previous training"

                job = {
                    "id": f"train_{uuid4().hex[:12]}",
                    "running": True,
                    "status": "running",
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "finished_at": None,
                    "last_message": "Queued",
                    "progress": [],
                    "error": None,
                    "result": None,
                    "cancel_requested": False,
                }
                self._training_job = job

            job_id = str(job["id"])

            def is_cancelled() -> bool:
                with self._training_lock:
                    current = self._training_job or {}
                    return (
                        current.get("id") != job_id
                        or bool(current.get("cancel_requested"))
                    )

            def progress(message: str) -> None:
                with self._training_lock:
                    if not self._training_job or self._training_job.get("id") != job_id:
                        return
                    entry = {
                        "at": datetime.now(timezone.utc).isoformat(),
                        "message": str(message),
                    }
                    self._training_job["last_message"] = str(message)
                    self._training_job["progress"] = [
                        *self._training_job.get("progress", [])[-24:],
                        entry,
                    ]

            def run() -> None:
                try:
                    progress("Starting training")
                    with self._training_run_lock:
                        if is_cancelled():
                            raise TrainingCancelled("Training superseded before start")
                        result = retrain_apps_pipeline(
                            progress=progress,
                            should_cancel=is_cancelled,
                        )
                    with self._training_lock:
                        if self._training_job and self._training_job.get("id") == job_id:
                            self._training_job.update(
                                {
                                    "running": False,
                                    "status": "completed",
                                    "finished_at": datetime.now(timezone.utc).isoformat(),
                                    "last_message": "Completed",
                                    "result": result,
                                    "cancel_requested": False,
                                }
                            )
                except TrainingCancelled as error:
                    with self._training_lock:
                        if self._training_job and self._training_job.get("id") == job_id:
                            self._training_job.update(
                                {
                                    "running": False,
                                    "status": "cancelled",
                                    "finished_at": datetime.now(timezone.utc).isoformat(),
                                    "last_message": "Cancelled",
                                    "error": str(error),
                                    "cancel_requested": False,
                                }
                            )
                except Exception as error:
                    with self._training_lock:
                        if self._training_job and self._training_job.get("id") == job_id:
                            self._training_job.update(
                                {
                                    "running": False,
                                    "status": "failed",
                                    "finished_at": datetime.now(timezone.utc).isoformat(),
                                    "last_message": "Failed",
                                    "error": str(error),
                                    "traceback": traceback.format_exc()[-6000:],
                                    "cancel_requested": False,
                                }
                            )

            thread = threading.Thread(target=run, name="beavis-training", daemon=True)
            thread.start()
            time.sleep(0.01)
            return ok(self._training_snapshot())
        except Exception as error:
            return fail(error, code="TRAINING_START_ERROR")

    def retrain_status(self) -> dict[str, Any]:
        try:
            return ok(self._training_snapshot())
        except Exception as error:
            return fail(error, code="TRAINING_STATUS_ERROR")

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
        desired_apps: list[dict[str, Any]] | None = None,
        retrain: bool = True,
        progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        try:
            def parse_change(item: dict[str, Any]) -> AppCatalogChange:
                path_value = str(item.get("path") or "").strip()
                return AppCatalogChange(
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

            if desired_apps is not None:
                result = sync_visible_user_apps(
                    SyncVisibleAppsRequest(
                        apps=[parse_change(item) for item in desired_apps],
                        retrain=retrain,
                    ),
                    progress=progress,
                )
            else:
                request_changes = [parse_change(item) for item in changes]
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
