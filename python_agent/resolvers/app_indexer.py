from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if sys.platform == "win32":
    import winreg
else:
    winreg = None  # type: ignore[assignment]

from python_agent.resolvers.app_catalog_overrides import DEFAULT_APP_OVERRIDES_PATH, active_disabled_app_ids
from python_agent.resolvers.user_app_catalog import DEFAULT_USER_APPS_PATH, load_user_apps
from python_agent.resolvers.windows_app_discovery import discover_windows_apps


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANUAL_CONFIG = PROJECT_ROOT / "configs" / "apps.manual.json"
DEFAULT_USER_APPS_CONFIG = DEFAULT_USER_APPS_PATH
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "python_agent" / "data" / "cache" / "apps_index.json"

SOURCE_PRIORITY = {
    "user": 110,
    "manual": 100,
    "start_apps": 75,
    "app_paths": 80,
    "start_menu": 70,
    "system": 60,
}

APP_SIGNATURES: dict[str, dict[str, list[str]]] = {
    "chrome": {"display_names": ["Google Chrome"], "executables": ["chrome.exe"]},
    "edge": {"display_names": ["Microsoft Edge"], "executables": ["msedge.exe"]},
    "firefox": {"display_names": ["Mozilla Firefox", "Firefox"], "executables": ["firefox.exe"]},
    "opera": {"display_names": ["Opera", "Opera GX"], "executables": ["opera.exe", "launcher.exe"]},
    "brave": {"display_names": ["Brave"], "executables": ["brave.exe"]},
    "yandex_browser": {"display_names": ["Yandex Browser"], "executables": ["browser.exe"]},
    "tor_browser": {"display_names": ["Tor Browser"], "executables": ["firefox.exe"]},
    "notepad": {"display_names": ["Notepad"], "executables": ["notepad.exe"]},
    "calculator": {"display_names": ["Calculator"], "executables": ["calc.exe", "calculator.exe"]},
    "explorer": {"display_names": ["File Explorer", "Windows Explorer"], "executables": ["explorer.exe"]},
    "cmd": {"display_names": ["Command Prompt"], "executables": ["cmd.exe"]},
    "powershell": {"display_names": ["Windows PowerShell", "PowerShell"], "executables": ["powershell.exe", "pwsh.exe"]},
    "terminal": {"display_names": ["Windows Terminal", "Terminal"], "executables": ["wt.exe"]},
    "settings": {"display_names": ["Settings"], "executables": ["systemsettings.exe"]},
    "task_manager": {"display_names": ["Task Manager"], "executables": ["taskmgr.exe"]},
    "control_panel": {"display_names": ["Control Panel"], "executables": ["control.exe"]},
    "paint": {"display_names": ["Paint"], "executables": ["mspaint.exe", "paint.exe"]},
    "snipping_tool": {"display_names": ["Snipping Tool"], "executables": ["snippingtool.exe"]},
    "photos": {"display_names": ["Microsoft Photos", "Photos"], "executables": ["photos.exe"]},
    "camera": {"display_names": ["Camera"], "executables": ["windowscamera.exe"]},
    "voice_recorder": {"display_names": ["Voice Recorder", "Sound Recorder"], "executables": ["soundrecorder.exe"]},
    "regedit": {"display_names": ["Registry Editor"], "executables": ["regedit.exe"]},
    "device_manager": {"display_names": ["Device Manager"], "executables": ["devmgmt.msc"]},
    "services": {"display_names": ["Services"], "executables": ["services.msc"]},
    "disk_management": {"display_names": ["Disk Management"], "executables": ["diskmgmt.msc"]},
    "event_viewer": {"display_names": ["Event Viewer"], "executables": ["eventvwr.msc"]},
    "microsoft_store": {"display_names": ["Microsoft Store"], "executables": ["winstore.app.exe"]},
    "word": {"display_names": ["Microsoft Word", "Word"], "executables": ["winword.exe"]},
    "excel": {"display_names": ["Microsoft Excel", "Excel"], "executables": ["excel.exe"]},
    "powerpoint": {"display_names": ["Microsoft PowerPoint", "PowerPoint"], "executables": ["powerpnt.exe"]},
    "outlook": {"display_names": ["Microsoft Outlook", "Outlook"], "executables": ["outlook.exe"]},
    "onenote": {"display_names": ["Microsoft OneNote", "OneNote"], "executables": ["onenote.exe"]},
    "access": {"display_names": ["Microsoft Access", "Access"], "executables": ["msaccess.exe"]},
    "visio": {"display_names": ["Microsoft Visio", "Visio"], "executables": ["visio.exe"]},
    "project": {"display_names": ["Microsoft Project", "Project"], "executables": ["winproj.exe"]},
    "telegram": {"display_names": ["Telegram Desktop", "Telegram"], "executables": ["telegram.exe"]},
    "discord": {"display_names": ["Discord"], "executables": ["discord.exe"]},
    "whatsapp": {"display_names": ["WhatsApp"], "executables": ["whatsapp.exe"]},
    "viber": {"display_names": ["Viber"], "executables": ["viber.exe"]},
    "skype": {"display_names": ["Skype"], "executables": ["skype.exe"]},
    "signal": {"display_names": ["Signal"], "executables": ["signal.exe"]},
    "slack": {"display_names": ["Slack"], "executables": ["slack.exe"]},
    "teams": {"display_names": ["Microsoft Teams", "Teams"], "executables": ["teams.exe", "ms-teams.exe"]},
    "zoom": {"display_names": ["Zoom"], "executables": ["zoom.exe"]},
    "photoshop": {"display_names": ["Adobe Photoshop", "Photoshop"], "executables": ["photoshop.exe"]},
    "illustrator": {"display_names": ["Adobe Illustrator", "Illustrator"], "executables": ["illustrator.exe"]},
    "premiere_pro": {"display_names": ["Adobe Premiere Pro", "Premiere Pro"], "executables": ["adobe premiere pro.exe"]},
    "after_effects": {"display_names": ["Adobe After Effects", "After Effects"], "executables": ["afterfx.exe"]},
    "audition": {"display_names": ["Adobe Audition", "Audition"], "executables": ["audition.exe"]},
    "lightroom": {"display_names": ["Adobe Lightroom", "Lightroom"], "executables": ["lightroom.exe"]},
    "acrobat_reader": {"display_names": ["Adobe Acrobat", "Acrobat Reader"], "executables": ["acrord32.exe", "acrobat.exe"]},
    "indesign": {"display_names": ["Adobe InDesign", "InDesign"], "executables": ["indesign.exe"]},
    "adobe_xd": {"display_names": ["Adobe XD"], "executables": ["xd.exe"]},
    "media_encoder": {"display_names": ["Adobe Media Encoder", "Media Encoder"], "executables": ["adobe media encoder.exe"]},
    "animate": {"display_names": ["Adobe Animate", "Animate"], "executables": ["animate.exe"]},
    "bridge": {"display_names": ["Adobe Bridge", "Bridge"], "executables": ["bridge.exe"]},
    "vscode": {"display_names": ["Visual Studio Code"], "executables": ["code.exe"]},
    "visual_studio": {"display_names": ["Visual Studio"], "executables": ["devenv.exe"]},
    "pycharm": {"display_names": ["PyCharm"], "executables": ["pycharm64.exe", "pycharm.exe"]},
    "intellij_idea": {"display_names": ["IntelliJ IDEA"], "executables": ["idea64.exe", "idea.exe"]},
    "webstorm": {"display_names": ["WebStorm"], "executables": ["webstorm64.exe", "webstorm.exe"]},
    "phpstorm": {"display_names": ["PhpStorm"], "executables": ["phpstorm64.exe", "phpstorm.exe"]},
    "clion": {"display_names": ["CLion"], "executables": ["clion64.exe", "clion.exe"]},
    "datagrip": {"display_names": ["DataGrip"], "executables": ["datagrip64.exe", "datagrip.exe"]},
    "android_studio": {"display_names": ["Android Studio"], "executables": ["studio64.exe", "studio.exe"]},
    "docker_desktop": {"display_names": ["Docker Desktop"], "executables": ["docker desktop.exe"]},
    "git_bash": {"display_names": ["Git Bash"], "executables": ["git-bash.exe"]},
    "github_desktop": {"display_names": ["GitHub Desktop"], "executables": ["githubdesktop.exe"]},
    "postman": {"display_names": ["Postman"], "executables": ["postman.exe"]},
    "dbeaver": {"display_names": ["DBeaver"], "executables": ["dbeaver.exe"]},
    "mysql_workbench": {"display_names": ["MySQL Workbench"], "executables": ["mysqlworkbench.exe"]},
    "pgadmin": {"display_names": ["pgAdmin"], "executables": ["pgadmin4.exe"]},
    "blender": {"display_names": ["Blender"], "executables": ["blender.exe"]},
    "figma": {"display_names": ["Figma"], "executables": ["figma.exe"]},
    "fusion_360": {"display_names": ["Fusion 360"], "executables": ["fusion360.exe"]},
    "autocad": {"display_names": ["AutoCAD"], "executables": ["acad.exe"]},
    "sketchup": {"display_names": ["SketchUp"], "executables": ["sketchup.exe"]},
    "max_3ds": {"display_names": ["3ds Max"], "executables": ["3dsmax.exe"]},
    "maya": {"display_names": ["Maya", "Autodesk Maya"], "executables": ["maya.exe"]},
    "cinema_4d": {"display_names": ["Cinema 4D"], "executables": ["cinema 4d.exe"]},
    "zbrush": {"display_names": ["ZBrush"], "executables": ["zbrush.exe"]},
    "substance_painter": {"display_names": ["Substance 3D Painter", "Substance Painter"], "executables": ["adobe substance 3d painter.exe"]},
    "unreal_engine": {"display_names": ["Unreal Engine"], "executables": ["unrealeditor.exe", "epicgameslauncher.exe"]},
    "unity": {"display_names": ["Unity Hub", "Unity"], "executables": ["unity hub.exe", "unity.exe"]},
    "godot": {"display_names": ["Godot"], "executables": ["godot.exe"]},
    "davinci_resolve": {"display_names": ["DaVinci Resolve"], "executables": ["resolve.exe"]},
    "obs_studio": {"display_names": ["OBS Studio"], "executables": ["obs64.exe", "obs32.exe"]},
    "vlc": {"display_names": ["VLC media player", "VLC"], "executables": ["vlc.exe"]},
    "spotify": {"display_names": ["Spotify"], "executables": ["spotify.exe"]},
    "steam": {"display_names": ["Steam"], "executables": ["steam.exe"]},
    "epic_games": {"display_names": ["Epic Games Launcher"], "executables": ["epicgameslauncher.exe"]},
    "winrar": {"display_names": ["WinRAR"], "executables": ["winrar.exe"]},
    "seven_zip": {"display_names": ["7-Zip"], "executables": ["7zfm.exe", "7zg.exe"]},
    "obsidian": {"display_names": ["Obsidian"], "executables": ["obsidian.exe"]},
    "notion": {"display_names": ["Notion"], "executables": ["notion.exe"]},
}


def no_console_kwargs() -> dict[str, int]:
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}


def compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def slugify(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_value.lower()).strip("_")
    return slug or "app"


def path_name(value: str) -> str:
    if not value:
        return ""
    return Path(value).name.lower()


def resolve_command(command: str) -> str:
    resolved = shutil.which(command)
    if resolved:
        return resolved

    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    candidates = [
        Path(system_root) / "System32" / command,
        Path(system_root) / "SysWOW64" / command,
        Path(system_root) / command,
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    return command


def is_existing_target(launch_type: str, target: str) -> bool:
    if launch_type == "uri":
        return bool(target)
    if not target:
        return False
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) and launch_type != "exe":
        return True
    if Path(target).exists():
        return True
    return shutil.which(target) is not None


def infer_app_id(
    display_name: str,
    launch_target: str,
    target_path: str = "",
    use_target_signature: bool = True,
) -> str:
    names = [display_name]
    if use_target_signature:
        names.extend([Path(launch_target).stem, Path(target_path).stem])
    compact_names = [compact(name) for name in names if name]
    executable_names = {path_name(launch_target), path_name(target_path)}

    if use_target_signature:
        for app_id, signature in APP_SIGNATURES.items():
            for executable in signature.get("executables", []):
                if executable.lower() in executable_names:
                    return app_id

    for app_id, signature in APP_SIGNATURES.items():
        for expected_name in signature.get("display_names", []):
            expected = compact(expected_name)
            if not expected:
                continue
            if any(name == expected or name.startswith(expected) for name in compact_names):
                return app_id

    base = display_name or Path(target_path).stem or Path(launch_target).stem
    return slugify(base)


def make_record(
    *,
    app_id: str,
    display_name: str,
    launch_type: str,
    launch_target: str,
    source: str,
    display_names: list[str] | None = None,
    target_path: str = "",
    arguments: str = "",
    working_directory: str = "",
) -> dict[str, Any]:
    launch_target = os.path.expandvars(launch_target)
    target_path = os.path.expandvars(target_path)
    working_directory = os.path.expandvars(working_directory)
    names = list(dict.fromkeys([name for name in (display_names or [display_name]) if name]))
    exists = is_existing_target(launch_type, launch_target)
    return {
        "app_id": app_id,
        "display_name": display_name,
        "display_names": names,
        "launch_type": launch_type,
        "launch_target": launch_target,
        "target_path": target_path,
        "arguments": arguments,
        "working_directory": working_directory,
        "source": source,
        "exists": exists,
        "priority": SOURCE_PRIORITY.get(source, 0),
    }


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


def scan_start_menu_shortcuts() -> list[dict[str, Any]]:
    if sys.platform != "win32":
        return []

    script = r"""
$OutputEncoding = [System.Text.UTF8Encoding]::new()
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$ErrorActionPreference = 'SilentlyContinue'
$shell = New-Object -ComObject WScript.Shell
$folders = @()
foreach ($base in @([Environment]::GetFolderPath('CommonStartMenu'), [Environment]::GetFolderPath('StartMenu'))) {
    if ($base) {
        $programs = Join-Path $base 'Programs'
        if (Test-Path $programs) {
            $folders += $programs
        }
    }
}
$result = @()
foreach ($folder in $folders) {
    Get-ChildItem -LiteralPath $folder -Recurse -Filter *.lnk -File | ForEach-Object {
        $shortcut = $shell.CreateShortcut($_.FullName)
        $result += [PSCustomObject]@{
            display_name = [System.IO.Path]::GetFileNameWithoutExtension($_.Name)
            shortcut_path = $_.FullName
            target_path = $shortcut.TargetPath
            arguments = $shortcut.Arguments
            working_directory = $shortcut.WorkingDirectory
        }
    }
}
@($result) | ConvertTo-Json -Depth 4
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

    records: list[dict[str, Any]] = []
    for item in parse_json_array(completed.stdout):
        display_name = str(item.get("display_name") or "").strip()
        shortcut_path = str(item.get("shortcut_path") or "").strip()
        target_path = str(item.get("target_path") or "").strip()
        if not display_name or not shortcut_path:
            continue
        if should_skip_shortcut(display_name, target_path):
            continue

        app_id = infer_app_id(
            display_name,
            shortcut_path,
            target_path,
            use_target_signature=False,
        )
        records.append(make_record(
            app_id=app_id,
            display_name=display_name,
            display_names=[display_name],
            launch_type="shortcut",
            launch_target=shortcut_path,
            target_path=target_path,
            arguments=str(item.get("arguments") or ""),
            working_directory=str(item.get("working_directory") or ""),
            source="start_menu",
        ))

    return records


def should_skip_shortcut(display_name: str, target_path: str) -> bool:
    haystack = f"{display_name} {Path(target_path).name}".lower()
    skip_terms = (
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
        "деинстал",
        "установ",
        "удалить",
        "удаление",
        "обнов",
    )
    return any(term in haystack for term in skip_terms)


def registry_views() -> list[int]:
    if winreg is None:
        return []

    views = [0]
    for view in ("KEY_WOW64_64KEY", "KEY_WOW64_32KEY"):
        flag = getattr(winreg, view, 0)
        if flag:
            views.append(flag)
    return list(dict.fromkeys(views))


def read_registry_value(key: Any, name: str) -> str:
    try:
        value, _kind = winreg.QueryValueEx(key, name)
    except OSError:
        return ""
    return str(value) if value is not None else ""


def scan_app_paths() -> list[dict[str, Any]]:
    if winreg is None:
        return []

    roots = [
        (winreg.HKEY_CURRENT_USER, "HKCU"),
        (winreg.HKEY_LOCAL_MACHINE, "HKLM"),
    ]
    subkey_path = r"Software\Microsoft\Windows\CurrentVersion\App Paths"
    records: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()

    for root, _root_name in roots:
        for view in registry_views():
            try:
                with winreg.OpenKey(root, subkey_path, 0, winreg.KEY_READ | view) as app_paths_key:
                    subkey_count, _value_count, _modified = winreg.QueryInfoKey(app_paths_key)
                    for index in range(subkey_count):
                        try:
                            executable_name = winreg.EnumKey(app_paths_key, index)
                            with winreg.OpenKey(app_paths_key, executable_name, 0, winreg.KEY_READ | view) as app_key:
                                target = read_registry_value(app_key, "")
                                if not target:
                                    continue
                                key = (executable_name.lower(), target.lower())
                                if key in seen_keys:
                                    continue
                                seen_keys.add(key)
                                display_name = Path(executable_name).stem
                                app_id = infer_app_id(display_name, target, target)
                                records.append(make_record(
                                    app_id=app_id,
                                    display_name=display_name,
                                    display_names=[display_name],
                                    launch_type="exe",
                                    launch_target=target,
                                    target_path=target,
                                    source="app_paths",
                                ))
                        except OSError:
                            continue
            except OSError:
                continue

    return records


def system_records() -> list[dict[str, Any]]:
    system_targets = [
        ("notepad", "Notepad", "exe", "notepad.exe"),
        ("calculator", "Calculator", "exe", "calc.exe"),
        ("explorer", "File Explorer", "exe", "explorer.exe"),
        ("cmd", "Command Prompt", "exe", "cmd.exe"),
        ("powershell", "Windows PowerShell", "exe", "powershell.exe"),
        ("terminal", "Windows Terminal", "exe", "wt.exe"),
        ("settings", "Settings", "uri", "ms-settings:"),
        ("task_manager", "Task Manager", "exe", "taskmgr.exe"),
        ("control_panel", "Control Panel", "exe", "control.exe"),
        ("paint", "Paint", "exe", "mspaint.exe"),
        ("snipping_tool", "Snipping Tool", "exe", "SnippingTool.exe"),
        ("regedit", "Registry Editor", "exe", "regedit.exe"),
        ("device_manager", "Device Manager", "exe", "devmgmt.msc"),
        ("services", "Services", "exe", "services.msc"),
        ("disk_management", "Disk Management", "exe", "diskmgmt.msc"),
        ("event_viewer", "Event Viewer", "exe", "eventvwr.msc"),
        ("microsoft_store", "Microsoft Store", "uri", "ms-windows-store:"),
    ]

    records = []
    for app_id, display_name, launch_type, target in system_targets:
        launch_target = resolve_command(target) if launch_type == "exe" else target
        records.append(make_record(
            app_id=app_id,
            display_name=display_name,
            display_names=[display_name],
            launch_type=launch_type,
            launch_target=launch_target,
            target_path=launch_target if launch_type == "exe" else "",
            source="system",
        ))

    return records


def load_manual_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Manual apps config must be a JSON list: {path}")

    records: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue

        app_id = str(item.get("app_id") or "").strip()
        launch_target = str(item.get("launch_target") or "").strip()
        if not app_id or not launch_target:
            continue

        display_names = item.get("display_names") or []
        if isinstance(display_names, str):
            display_names = [display_names]
        if not isinstance(display_names, list):
            display_names = []

        display_names = [str(name).strip() for name in display_names if str(name).strip()]
        display_name = str(item.get("display_name") or "").strip() or (display_names[0] if display_names else app_id)
        launch_type = str(item.get("launch_type") or "exe").strip()

        records.append(make_record(
            app_id=app_id,
            display_name=display_name,
            display_names=display_names or [display_name],
            launch_type=launch_type,
            launch_target=launch_target,
            target_path=str(item.get("target_path") or launch_target),
            arguments=str(item.get("arguments") or ""),
            working_directory=str(item.get("working_directory") or ""),
            source="manual",
        ))

    return records


def load_user_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in load_user_apps(path):
        records.append(make_record(
            app_id=item.app_id,
            display_name=item.display_name,
            display_names=[item.display_name, *item.speech_forms],
            launch_type=item.launch_type,
            launch_target=item.launch_target,
            target_path=item.target_path or item.launch_target,
            arguments="",
            working_directory=item.working_directory,
            source="user",
        ))

    return records


def load_windows_app_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in discover_windows_apps():
        app_id = infer_app_id(
            item.display_name,
            item.launch_target,
            item.windows_app_id,
            use_target_signature=False,
        )
        records.append(make_record(
            app_id=app_id,
            display_name=item.display_name,
            display_names=[item.display_name],
            launch_type=item.launch_type,
            launch_target=item.launch_target,
            target_path=item.windows_app_id,
            source="start_apps",
        ))
    return records


def dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for record in records:
        key = (
            str(record.get("app_id", "")),
            str(record.get("launch_type", "")),
            str(record.get("launch_target", "")).lower(),
            str(record.get("arguments", "")),
        )
        existing = out.get(key)
        if existing is None or int(record.get("priority", 0)) > int(existing.get("priority", 0)):
            out[key] = record

    return sorted(
        out.values(),
        key=lambda item: (
            str(item.get("app_id", "")),
            -int(item.get("priority", 0)),
            str(item.get("display_name", "")),
        ),
    )


def filter_disabled_records(
    records: list[dict[str, Any]],
    overrides_config: Path = DEFAULT_APP_OVERRIDES_PATH,
) -> list[dict[str, Any]]:
    disabled = active_disabled_app_ids(overrides_config)
    if not disabled:
        return records

    return [
        record
        for record in records
        if str(record.get("source") or "") == "user"
        or str(record.get("app_id") or "") not in disabled
    ]


def build_index(
    manual_config: Path,
    user_apps_config: Path = DEFAULT_USER_APPS_CONFIG,
    overrides_config: Path = DEFAULT_APP_OVERRIDES_PATH,
) -> dict[str, Any]:
    records = []
    records.extend(system_records())
    records.extend(scan_app_paths())
    records.extend(load_windows_app_records())
    records.extend(scan_start_menu_shortcuts())
    records.extend(load_manual_records(manual_config))
    records.extend(load_user_records(user_apps_config))
    records = filter_disabled_records(records, overrides_config)
    records = dedupe_records(records)

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manual_config": str(manual_config),
        "user_apps_config": str(user_apps_config),
        "overrides_config": str(overrides_config),
        "records": records,
        "summary": {
            "records_total": len(records),
            "records_existing": sum(1 for record in records if record.get("exists")),
            "app_ids_total": len({record.get("app_id") for record in records}),
            "sources": {
                source: sum(1 for record in records if record.get("source") == source)
                for source in sorted(SOURCE_PRIORITY)
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Beavis Agent Windows apps index")
    parser.add_argument("--manual-config", type=Path, default=DEFAULT_MANUAL_CONFIG)
    parser.add_argument("--user-apps-config", type=Path, default=DEFAULT_USER_APPS_CONFIG)
    parser.add_argument("--overrides-config", type=Path, default=DEFAULT_APP_OVERRIDES_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    index = build_index(args.manual_config, args.user_apps_config, args.overrides_config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "output": str(args.output),
        **index["summary"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
