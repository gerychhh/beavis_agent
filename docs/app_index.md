# App Index

`open_app` has two separate responsibilities:

```text
Python open_app extractor -> app_id
C++ AppResolver -> launch target
Window lookup -> focus existing window or launch target
```

The model does not know Windows paths. It returns a stable id:

```json
{"app_id": "google_chrome"}
```

## Sources

The local app index is generated from:

```text
Start Menu shortcuts
Registry App Paths
Windows apps
configs/apps.manual.json
python_agent/data/user_apps/apps.json
```

Refresh the index:

```powershell
python -m python_agent.resolvers.app_indexer
```

or:

```powershell
.\scripts\dev.ps1 index
```

Generated output:

```text
python_agent/data/cache/apps_index.json
```

This file is ignored by Git.

## Manual Apps

Use `configs/apps.manual.json` for programs that Windows does not expose well.

```json
[
  {
    "app_id": "my_tool",
    "display_names": ["My Tool", "My Tool 2026"],
    "launch_type": "exe",
    "launch_target": "D:\\Tools\\MyTool\\mytool.exe",
    "arguments": "",
    "working_directory": "D:\\Tools\\MyTool"
  }
]
```

`display_names` are application names. User speech aliases belong in datasets or
the user app catalog.

## Runtime Behavior

At execution time `open_app` tries to find an existing visible top-level window
for the resolved app. If found, it restores/focuses that window. If not found,
it launches the configured target.
