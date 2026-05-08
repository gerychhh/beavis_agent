# Beavis Desktop UI

The active desktop UI lives in `desktop_ui/`.

It is a Tauri 2 shell with a Vite/React frontend. The UI talks to Python through
the JSON-lines bridge in `python_agent/bridge/stdio_server.py`; Python then uses
the same command pipeline and C++ runtime as the CLI.

Run in development mode:

```powershell
.\scripts\dev.ps1 ui-install
.\scripts\dev.ps1 ui-dev
```

Build a production binary:

```powershell
.\scripts\dev.ps1 ui-build
```

Check the Python bridge used by the UI:

```powershell
.\scripts\dev.ps1 ui-health
```

Included UI responsibilities:

```text
command input and execution
global shortcuts through Tauri
voice controls
settings
history
local application management
retraining status
```

The UI does not execute Windows actions directly. It calls the Python API bridge,
which emits `ToolCall` JSON and sends execution to the C++ runtime.
