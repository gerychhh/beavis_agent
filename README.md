# Beavis Agent

Beavis Agent is a local Windows desktop assistant. It understands noisy text or
voice commands, converts them into strict JSON, and executes Windows actions
through a C++ runtime.

```text
UI / Voice / CLI
-> Python NLU
-> CommandDecision / ToolCall JSON
-> CommandExecutor
-> C++ Runtime
-> Windows API
-> SkillResult JSON
-> Logs
```

The boundary is intentional:

```text
Python understands commands.
C++ executes Windows actions.
JSON is the contract.
UI is only an interface.
```

The NLU must tolerate imperfect user input: typos, wake words, mixed
Russian/English app names, and rough phrasing. Do not replace working ML
behavior with narrow regex rules unless the behavior is proven equivalent.

## Current Skills

| Skill | Purpose | Example |
|---|---|---|
| `open_app` | Open or focus an application | `открой хром` |
| `volume_set` | Set or change system volume | `звук на 50` |
| `window_control` | Close, minimize, maximize, or restore a window | `сверни телеграм` |
| `window_layout` | Move or arrange windows | `bavis сделай справо codex` |

Planner/multi-step planning is not part of the current architecture.

## Repository Layout

```text
configs/              Shared configuration and manual app records
cpp_runtime/          C++ JSON runtime and Windows skills
desktop_ui/           Tauri + Vite desktop UI
docs/                 Architecture and developer documentation
python_agent/api/     Stable Python API services
python_agent/bridge/  JSON-lines bridge used by the UI
python_agent/core/    Command pipeline, executor, schemas, logging
python_agent/nlu/     Normalizer, classifier, legacy extractor modules
python_agent/skills/  Skill specs and modular extractor entrypoints
python_agent/training/Dataset generation, training, and tests
python_agent/voice/   Audio capture, STT, wake-word handling
scripts/dev.ps1       Main Windows developer helper
```

## Requirements

Use Windows and PowerShell.

Required tools:

```text
Python 3.10 or 3.11
Visual Studio 2022 C++ build tools
CMake
Ninja
Node.js
Rust toolchain for Tauri desktop builds
```

Install Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

Use the same Python environment for training, tests, the CLI, and the desktop
app. If the desktop app works but a shell command fails to load a `.joblib`
model, the shell is probably using a different Python/sklearn environment.

## Build And Run

First run from the repository root:

```powershell
.\scripts\dev.ps1 setup
.\scripts\dev.ps1 build
.\scripts\dev.ps1 index
.\scripts\dev.ps1 test
.\scripts\dev.ps1 smoke
```

Shortcut:

```powershell
.\scripts\dev.ps1 all
```

Build a `ToolCall` without executing Windows actions:

```powershell
python -m python_agent.main "сверни телеграм" --no-log
```

Execute through the C++ runtime:

```powershell
python -m python_agent.main "сверни телеграм" --execute
```

Run the desktop UI:

```powershell
.\scripts\dev.ps1 ui-install
.\scripts\dev.ps1 ui-dev
```

Build frontend assets only:

```powershell
cd desktop_ui
npm run build
```

Build the Tauri desktop app:

```powershell
.\scripts\dev.ps1 ui-build
```

More setup, build, run, and troubleshooting details are in
`docs/SETUP_AND_RUN.md`.

## Tests

Stable daily checks:

```powershell
.\scripts\dev.ps1 test
.\scripts\dev.ps1 smoke
.\scripts\dev.ps1 build
cd desktop_ui
npm run build
```

Golden command tests:

```powershell
python python_agent\training\test_golden_commands.py
```

The golden dataset lives at:

```text
python_agent/data/eval/golden_commands.jsonl
```

It checks `ready`, `rejected`, and `needs_clarification` decisions.

`.\scripts\dev.ps1 test-all` also runs the legacy `volume_set` argument model
test. That test can fail when local sklearn/joblib versions do not match the
model file. Keep the runtime environment consistent before treating that as a
behavior regression.

## Adding A Skill

Short version:

```text
1. Create python_agent/skills/<skill_name>/
2. Add spec.py with SkillSpec
3. Add extractor.py
4. Add examples.py and golden cases
5. Add C++ skill
6. Add C++ ArgsValidator rules
7. Register the skill in Python and C++
8. Update COMMAND_PROTOCOL.md
9. Run tests, smoke, C++ build, and UI build
```

Full guide: `docs/SKILL_DEVELOPMENT.md`.

## Models And Local Data

Generated models and local runtime data are ignored by Git:

```text
python_agent/models/*.joblib
python_agent/models/stt/*
python_agent/data/cache/
python_agent/data/logs/
python_agent/data/settings/
python_agent/data/user_apps/
external_data/
```

Keep only placeholders under `python_agent/models/`:

```text
python_agent/models/.gitkeep
python_agent/models/stt/.gitkeep
```

Do not commit generated models, logs, local app indexes, user app paths, build
output, or downloaded STT models.

## Documentation Map

Start here:

```text
docs/README.md              Documentation index
docs/SETUP_AND_RUN.md       Build, run, test, and troubleshooting
docs/ARCHITECTURE.md        Layer boundaries and code ownership
docs/COMMAND_PROTOCOL.md    ToolCall, CommandDecision, SkillResult
docs/SKILL_DEVELOPMENT.md   How to add or change a skill
docs/MODEL_STORAGE.md       Model artifact policy
docs/REFACTOR_PLAN.md       Current refactor direction
docs/ui.md                  Desktop UI notes
docs/user_apps.md           User-added local apps
docs/app_index.md           App indexing and runtime resolution
```

## Development Rules

Do:

```text
Keep Python as the understanding layer.
Keep C++ as the Windows execution layer.
Keep JSON as the contract between them.
Keep each skill's schema and examples near that skill.
Keep compatibility wrappers until all callers are migrated.
```

Do not:

```text
Execute Windows actions directly from UI or voice code.
Move ML/NLU into C++.
Move Windows API calls into Python.
Commit generated models, logs, app indexes, or build output.
Add Planner during this simplification pass.
```
