# Beavis Agent

Local Windows desktop assistant.

## Quick Start

Run everything needed for a first local check:

```powershell
.\scripts\dev.ps1 all
```

Daily commands:

```powershell
.\scripts\dev.ps1 build
.\scripts\dev.ps1 test
.\scripts\dev.ps1 run "запусти блокнот" --execute
.\scripts\dev.ps1 ui
```

Useful tasks:

```powershell
.\scripts\dev.ps1 setup       # install Python dependencies
.\scripts\dev.ps1 build       # build C++ runtime
.\scripts\dev.ps1 index       # scan installed apps
.\scripts\dev.ps1 smoke       # pipeline checks without execution
.\scripts\dev.ps1 train       # retrain window_control + skill classifier
.\scripts\dev.ps1 clean       # remove local build/cache files
```

User applications can be added from the UI or with:

```powershell
python -m python_agent.training.add_user_app --path "D:\Tools\App\app.exe" --display-name "App" --speech-form "мой апп"
```

The default UI hotkey is configurable in the Settings tab:

```text
Ctrl+Alt+Space
```

## Manual Run

Without execution:

```powershell
python -m python_agent.main "сверни окно"
```

With execution:

```powershell
python -m python_agent.main "сверни блокнот" --execute
```
