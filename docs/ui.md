# Desktop UI

The active desktop UI lives in `desktop_ui/`.

It is a Tauri 2 shell with a Vite/React frontend. The UI talks to Python through
the JSON-lines bridge and never executes Windows actions directly.

Flow:

```text
React UI
-> Tauri Rust bridge
-> python_agent/bridge/stdio_server.py
-> python_agent/bridge/router.py
-> python_agent/api/*
-> CommandPipeline / services
```

Run in development mode:

```powershell
.\scripts\dev.ps1 ui-install
.\scripts\dev.ps1 ui-dev
```

Build frontend assets:

```powershell
cd desktop_ui
npm run build
```

Build Tauri app:

```powershell
.\scripts\dev.ps1 ui-build
```

Check Python bridge health:

```powershell
.\scripts\dev.ps1 ui-health
```

UI responsibilities:

```text
command input
global shortcuts
voice controls
settings
history
local application management
retraining status
```

When splitting UI files, move code without changing design or behavior first.
