from __future__ import annotations

import threading
import time
import traceback
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from python_agent.api.commands import CommandsApi
from python_agent.api.result import fail, ok
from python_agent.resolvers.site_catalog_service import (
    SiteCatalogService,
    SiteRecord,
    normalize_site_id,
)
from python_agent.training.add_user_app import TrainingCancelled, retrain_apps_pipeline


class SitesApi:
    def __init__(self) -> None:
        self._training_lock = threading.Lock()
        self._training_run_lock = threading.Lock()
        self._training_job: dict[str, Any] | None = None
        self._commands_api: CommandsApi | None = None

    def list_user_sites(self) -> dict[str, Any]:
        try:
            service = SiteCatalogService()
            return ok([record.to_dict() for record in service.get_all_sites() if record.enabled])
        except Exception as error:
            return fail(error, code="LIST_SITES_ERROR")

    def apply_changes(
        self,
        changes: list[dict[str, Any]],
        retrain: bool = False,
    ) -> dict[str, Any]:
        try:
            if not changes:
                raise ValueError("No site catalog changes to apply")

            service = SiteCatalogService()
            applied: list[dict[str, Any]] = []

            for item in changes:
                operation = str(item.get("operation") or "").strip().lower()
                site_id = normalize_site_id(str(item.get("site_id") or ""))

                if operation == "add":
                    record = SiteRecord(
                        site_id=site_id,
                        display_name=str(item.get("display_name") or "").strip(),
                        source=str(item.get("source") or "user").strip().lower(),
                        enabled=bool(item.get("enabled", True)),
                        base_url=str(item.get("base_url") or "").strip(),
                        speech_forms=[str(value) for value in item.get("speech_forms") or []],
                        priority=int(item.get("priority") or 300),
                    )
                    saved = service.add_site(record)
                    applied.append({"operation": "add", "site_id": saved.site_id})
                    continue

                if not site_id:
                    raise ValueError("site_id is required")

                if operation == "update":
                    saved = service.update_site(
                        site_id,
                        display_name=str(item.get("display_name") or "").strip(),
                        base_url=str(item.get("base_url") or "").strip(),
                        speech_forms=[str(value) for value in item.get("speech_forms") or []],
                        enabled=bool(item.get("enabled", True)),
                        priority=int(item.get("priority") or 300),
                    )
                    applied.append({"operation": "update", "site_id": saved.site_id})
                elif operation == "delete":
                    deleted = service.delete_site(site_id)
                    applied.append({"operation": "delete", "site_id": deleted.site_id})
                else:
                    raise ValueError(f"Unsupported site catalog operation: {operation}")

            payload = {
                "changes": applied,
                "sites": [record.to_dict() for record in service.get_all_sites() if record.enabled],
            }
            if retrain:
                payload["training"] = self.retrain_start().get("data")
            return ok(payload)
        except Exception as error:
            return fail(error, code="APPLY_SITE_CHANGES_ERROR")

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
                    return current.get("id") != job_id or bool(current.get("cancel_requested"))

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
                    try:
                        if self._commands_api is not None:
                            self._commands_api.reload()
                    except Exception:
                        pass
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

            thread = threading.Thread(target=run, name="beavis-sites-training", daemon=True)
            thread.start()
            time.sleep(0.01)
            return ok(self._training_snapshot())
        except Exception as error:
            return fail(error, code="SITE_TRAINING_START_ERROR")

    def retrain_status(self) -> dict[str, Any]:
        try:
            return ok(self._training_snapshot())
        except Exception as error:
            return fail(error, code="SITE_TRAINING_STATUS_ERROR")

    def _training_snapshot(self) -> dict[str, Any]:
        with self._training_lock:
            return dict(self._training_job or {"running": False, "status": "idle"})
