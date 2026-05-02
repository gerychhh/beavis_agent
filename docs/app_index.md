# App Index

`open_app` is split into two separate jobs:

```text
Python open_app_arg_model -> app_id
C++ AppResolver -> launch target
C++ window lookup -> focus existing window or launch target
```

The model does not know Windows paths. It only returns a canonical value like:

```json
{"app_id": "chrome"}
```

The local app index is generated from Windows sources:

```text
Start Menu .lnk shortcuts
Registry App Paths
Built-in Windows launch targets
configs/apps.manual.json
python_agent/data/user_apps/apps.json
```

Build or refresh the index:

```bash
python -m python_agent.resolvers.app_indexer
```

Output:

```text
python_agent/data/cache/apps_index.json
```

That file is machine-specific and is ignored by git.

At runtime `open_app` first searches visible top-level windows that match the
resolved app path, executable name, app id, or display name. A found window is
restored if minimized and brought to the foreground. A new process is launched
only when no matching window exists.

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

`display_names` are names from the system or installer, not user speech aliases.
Speech variants belong in the model dataset.

User-added applications are stored separately in
`python_agent/data/user_apps/apps.json`. That file may include `speech_forms`
for model training, but the resolver still uses only the stable `app_id` and
launch target.
