# Setup And Run

This document describes how to install, build, run, and verify Beavis Agent on a
Windows development machine.

## Requirements

```text
Windows 10/11
PowerShell
Python 3.10 or 3.11
Visual Studio 2022 with C++ build tools
CMake
Ninja
Node.js
Rust toolchain for Tauri desktop builds
```

Useful environment overrides:

```text
BEAVIS_VS_INSTALL   Visual Studio install directory
BEAVIS_VSDEVCMD     Full path to VsDevCmd.bat
BEAVIS_CMAKE        Full path to cmake.exe
BEAVIS_NINJA        Full path to ninja.exe
```

## Python Setup

From the repository root:

```powershell
python -m pip install -r requirements.txt
```

Use one Python environment consistently for:

```text
CLI runs
desktop UI bridge
training scripts
model tests
```

If a `.joblib` model loads in the desktop app but not in PowerShell, check which
Python and sklearn/joblib versions each environment uses.

## C++ Runtime Build

Recommended:

```powershell
.\scripts\dev.ps1 build
```

What it does:

```text
find Visual Studio tools
configure cpp_runtime/build with CMake + Ninja if needed
build beavis_runtime.exe
```

Manual equivalent:

```powershell
.\scripts\dev.ps1 configure
.\scripts\dev.ps1 build
```

## App Index

The Python layer resolves messy app names to stable `app_id` values. The C++
runtime resolves `app_id` to a launch target.

Refresh the local app index:

```powershell
.\scripts\dev.ps1 index
```

Generated output:

```text
python_agent/data/cache/apps_index.json
```

This file is local and ignored by Git.

## CLI Usage

Build JSON without executing a Windows action:

```powershell
python -m python_agent.main "открой хром" --no-log
```

Execute through the C++ runtime:

```powershell
python -m python_agent.main "сверни телеграм" --execute
```

Use an explicit runtime path:

```powershell
python -m python_agent.main "сверни телеграм" --execute --executor cpp_runtime\build\beavis_runtime.exe
```

Use the dev helper:

```powershell
.\scripts\dev.ps1 run "открой хром" --execute
```

## Python Bridge

Check bridge health:

```powershell
python -m python_agent.bridge.oneshot system.health
```

Expected result:

```json
{
  "ok": true,
  "data": {
    "service": "beavis_api",
    "status": "ready"
  }
}
```

Useful API methods:

```text
commands.build_decision
commands.build_tool_call
commands.run
apps.list_windows_apps
voice.listen_once
settings.load
history.list
```

## Desktop UI

Install UI dependencies:

```powershell
.\scripts\dev.ps1 ui-install
```

Run the Tauri desktop app in development:

```powershell
.\scripts\dev.ps1 ui-dev
```

Build frontend assets only:

```powershell
cd desktop_ui
npm run build
```

Build the full Tauri app:

```powershell
.\scripts\dev.ps1 ui-build
```

## Voice

Run a manual microphone/STT check:

```powershell
.\scripts\dev.ps1 voice-test
```

Voice uses the same command pipeline after transcription:

```text
microphone -> STT -> normalized text -> CommandPipeline
```

## Tests

Stable daily tests:

```powershell
.\scripts\dev.ps1 test
```

Smoke tests:

```powershell
.\scripts\dev.ps1 smoke
```

Golden command tests only:

```powershell
python python_agent\training\test_golden_commands.py
```

Full local check before a larger refactor:

```powershell
python -m compileall python_agent
python python_agent\training\test_golden_commands.py
.\scripts\dev.ps1 test
.\scripts\dev.ps1 smoke
.\scripts\dev.ps1 build
cd desktop_ui
npm run build
```

Optional legacy volume model test:

```powershell
.\scripts\dev.ps1 test-all
```

`test-all` includes `test_volume_set_arg_model.py`. If it fails with sklearn or
joblib loading errors while the app works, align the local Python environment or
retrain/resave the model before changing runtime behavior.

## Training

Current grouped training helper:

```powershell
.\scripts\dev.ps1 train
```

Individual scripts still exist:

```powershell
python python_agent\training\generate_skill_classifier_dataset.py
python python_agent\training\train_skill_classifier.py
python python_agent\training\test_skill_classifier.py

python python_agent\training\generate_window_control_dataset.py
python python_agent\training\train_window_control_arg_model.py
python python_agent\training\test_window_control_arg_model.py

python python_agent\training\generate_window_layout_dataset.py
python python_agent\training\train_window_layout_arg_model.py
python python_agent\training\test_window_layout_arg_model.py
```

Generated models are local artifacts and are ignored by Git.

## Clean Generated Files

Remove local build/cache/log files:

```powershell
.\scripts\dev.ps1 clean
```

This removes generated files inside the repository only. It does not remove
tracked source files.

## Troubleshooting

If C++ build tools are not found:

```text
install Visual Studio 2022 C++ workload
or set BEAVIS_VS_INSTALL / BEAVIS_VSDEVCMD / BEAVIS_CMAKE / BEAVIS_NINJA
```

If Russian text appears broken in a raw PowerShell command:

```text
use scripts/dev.ps1 helpers
keep PowerShell output encoding as UTF-8
avoid copying mojibake examples into docs or datasets
```

If a command is understood in the app but not in shell:

```text
check Python executable
check installed sklearn/joblib versions
check generated model files under python_agent/models/
run python -m pip install -r requirements.txt in the same environment
```

If the UI starts but Python calls fail:

```powershell
python -m python_agent.bridge.oneshot system.health
.\scripts\dev.ps1 ui-health
```

If `open_app` cannot launch a program:

```powershell
.\scripts\dev.ps1 index
```

Then inspect:

```text
python_agent/data/cache/apps_index.json
configs/apps.manual.json
python_agent/data/user_apps/apps.json
```

