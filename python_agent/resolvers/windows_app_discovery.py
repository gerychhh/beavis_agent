from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class WindowsAppEntry:
    display_name: str
    windows_app_id: str
    launch_type: str
    launch_target: str
    source: str

    def to_dict(self) -> dict[str, str]:
        return {
            "display_name": self.display_name,
            "windows_app_id": self.windows_app_id,
            "launch_type": self.launch_type,
            "launch_target": self.launch_target,
            "source": self.source,
        }


SKIP_TERMS = (
    "uninstall",
    "uninstaller",
    "unins",
    "install",
    "installer",
    "setup",
    "update",
    "updater",
    "remove",
    "modify",
    "readme",
    "read me",
    "documentation",
    "docs",
    "faq",
    "homepage",
    "website",
    "help",
    "support",
    "деинстал",
    "установ",
    "удалить",
    "удаление",
    "обнов",
    "справка",
    "документац",
)


def no_console_kwargs() -> dict[str, int]:
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}


def discover_windows_apps() -> list[WindowsAppEntry]:
    if sys.platform != "win32":
        return []

    entries: list[WindowsAppEntry] = []
    entries.extend(scan_get_start_apps())
    entries.extend(scan_apps_folder())
    return dedupe_entries(entries)


def scan_get_start_apps() -> list[WindowsAppEntry]:
    script = r"""
$OutputEncoding = [System.Text.UTF8Encoding]::new()
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$ErrorActionPreference = 'SilentlyContinue'
Get-StartApps | Select-Object Name, AppID | ConvertTo-Json -Depth 3
"""
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=60,
        **no_console_kwargs(),
    )
    if completed.returncode != 0:
        return []

    entries: list[WindowsAppEntry] = []
    for item in parse_json_array(completed.stdout):
        name = str(item.get("Name") or "").strip()
        app_id = str(item.get("AppID") or "").strip()
        entry = make_entry(name, app_id, "start_apps")
        if entry is not None:
            entries.append(entry)
    return entries


def scan_apps_folder() -> list[WindowsAppEntry]:
    script = r"""
$OutputEncoding = [System.Text.UTF8Encoding]::new()
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$ErrorActionPreference = 'SilentlyContinue'
$shell = New-Object -ComObject Shell.Application
$folder = $shell.Namespace('shell:AppsFolder')
$result = @()
if ($folder) {
    foreach ($item in $folder.Items()) {
        $result += [PSCustomObject]@{
            Name = $item.Name
            Path = $item.Path
        }
    }
}
@($result) | ConvertTo-Json -Depth 3
"""
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=60,
        **no_console_kwargs(),
    )
    if completed.returncode != 0:
        return []

    entries: list[WindowsAppEntry] = []
    for item in parse_json_array(completed.stdout):
        name = str(item.get("Name") or "").strip()
        app_id = str(item.get("Path") or "").strip()
        entry = make_entry(name, app_id, "apps_folder")
        if entry is not None:
            entries.append(entry)
    return entries


def make_entry(display_name: str, windows_app_id: str, source: str) -> WindowsAppEntry | None:
    display_name = repair_mojibake(display_name.strip())
    windows_app_id = windows_app_id.strip()
    if not display_name or not windows_app_id:
        return None
    if should_skip_entry(display_name, windows_app_id):
        return None

    launch_type = infer_launch_type(windows_app_id)
    launch_target = infer_launch_target(launch_type, windows_app_id)
    return WindowsAppEntry(
        display_name=display_name,
        windows_app_id=windows_app_id,
        launch_type=launch_type,
        launch_target=launch_target,
        source=source,
    )


def repair_mojibake(value: str) -> str:
    if not value:
        return value
    try:
        repaired = value.encode("cp1251").decode("utf-8")
    except UnicodeError:
        return value
    if mojibake_score(value) >= 2 and mojibake_score(repaired) < mojibake_score(value):
        return repaired
    return value


def mojibake_score(value: str) -> int:
    return value.count("Р ") + value.count("РЎ") + value.count("Гђ") + value.count("Г‘")


def infer_launch_type(windows_app_id: str) -> str:
    if re.match(r"^https?://", windows_app_id, re.IGNORECASE):
        return "uri"
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", windows_app_id):
        return "uri"
    if windows_app_id.lower().endswith(".lnk"):
        return "shortcut"
    if looks_like_path(windows_app_id):
        return "exe"
    return "apps_folder"


def infer_launch_target(launch_type: str, windows_app_id: str) -> str:
    if launch_type == "apps_folder":
        return f"shell:AppsFolder\\{windows_app_id}"
    return windows_app_id


def looks_like_path(value: str) -> bool:
    if re.match(r"^[a-zA-Z]:\\", value):
        return True
    if value.startswith("\\\\"):
        return True
    if value.startswith("{") and "\\" in value:
        return True
    return Path(value).suffix.lower() in {".exe", ".msc", ".bat", ".cmd"}


def should_skip_entry(display_name: str, windows_app_id: str) -> bool:
    haystack = f"{display_name} {windows_app_id}".lower()
    if any(term in haystack for term in SKIP_TERMS):
        return True
    if re.match(r"^https?://", windows_app_id, re.IGNORECASE):
        return True
    return False


def dedupe_entries(entries: list[WindowsAppEntry]) -> list[WindowsAppEntry]:
    by_key: dict[tuple[str, str], WindowsAppEntry] = {}
    source_rank = {"start_apps": 2, "apps_folder": 1}
    for entry in entries:
        key = (entry.display_name.casefold(), entry.windows_app_id.casefold())
        existing = by_key.get(key)
        if existing is None or source_rank.get(entry.source, 0) > source_rank.get(existing.source, 0):
            by_key[key] = entry
    return sorted(by_key.values(), key=lambda item: (item.display_name.casefold(), item.windows_app_id.casefold()))


def parse_json_array(payload: str) -> list[dict[str, Any]]:
    stripped = payload.strip()
    if not stripped:
        return []
    data = json.loads(stripped)
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        return [data]
    return []
