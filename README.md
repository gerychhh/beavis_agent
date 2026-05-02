# Beavis Agent

Local Windows desktop assistant with text and voice input.

Beavis Agent converts imperfect natural-language commands into strict JSON `ToolCall` objects, sends them to a C++ runtime, executes Windows actions, and logs the result for debugging and future model improvement.

## Current state

The project currently contains:

- Python NLU pipeline
- PySide6 desktop UI
- global text hotkey overlay
- voice input through `faster-whisper`
- C++ runtime for Windows actions
- app indexing from Windows sources
- ML models for skill classification and argument extraction
- developer automation through `scripts/dev.ps1`

Current supported skills:

| Skill | Meaning | Example |
|---|---|---|
| `open_app` | Open or focus an application | `запусти блокнот` |
| `volume_set` | Set or change system volume | `звук на 50` |
| `window_control` | Close/minimize/maximize/restore a window | `сверни телеграм` |
| `window_layout` | Place windows on screen | `телеграм слева, vscode справа` |

## Architecture

```text
Text / Voice input
→ Python NLU pipeline
→ ToolCall JSON
→ C++ runtime
→ Windows skill execution
→ SkillResult JSON
→ Python logger
```

Python is responsible for:

```text
normalization
skill classification
argument extraction
training datasets
model training
UI
voice transcription
logging
```

C++ is responsible for:

```text
argument validation
skill registry
safe execution boundary
Windows API calls
application launching
volume control
window control
window layout
```

## Repository structure

```text
beavis_agent/
├── configs/
│   ├── apps.manual.json
│   └── normalizer.json
│
├── cpp_runtime/
│   ├── CMakeLists.txt
│   └── src/
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── COMMAND_PROTOCOL.md
│   ├── MODEL_STORAGE.md
│   └── PROJECT_CONTEXT.md
│
├── python_agent/
│   ├── core/
│   ├── data/
│   ├── ml_models/
│   ├── models/
│   ├── nlu/
│   ├── resolvers/
│   ├── training/
│   ├── ui/
│   ├── voice/
│   ├── cpp_client.py
│   └── main.py
│
├── scripts/
│   └── dev.ps1
│
├── .gitignore
├── README.md
└── requirements.txt
```

## Important model policy

Generated model files are local artifacts and should not be committed:

```text
python_agent/models/*.joblib
python_agent/models/stt/*
```

The repository should keep only folder placeholders:

```text
python_agent/models/.gitkeep
python_agent/models/stt/.gitkeep
```

See:

```text
docs/MODEL_STORAGE.md
```

## Requirements

Recommended environment:

```text
Windows 10/11
Python 3.10 or 3.11
PowerShell
Visual Studio 2022 with C++ build tools
CMake
Ninja
```

Python dependencies are installed from:

```text
requirements.txt
```

C++ dependencies are handled by CMake. The C++ runtime downloads `nlohmann/json` through `FetchContent`.

## Quick start

From the repository root:

```powershell
.\scripts\dev.ps1 all
```

This runs:

```text
setup
build
index
test
smoke
```

## Daily commands

```powershell
.\scripts\dev.ps1 setup
.\scripts\dev.ps1 build
.\scripts\dev.ps1 index
.\scripts\dev.ps1 train
.\scripts\dev.ps1 test
.\scripts\dev.ps1 smoke
.\scripts\dev.ps1 run "запусти блокнот" --execute
.\scripts\dev.ps1 ui
```

## Manual setup

Install Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

Build C++ runtime:

```powershell
.\scripts\dev.ps1 build
```

Index installed Windows applications:

```powershell
.\scripts\dev.ps1 index
```

Train local models:

```powershell
.\scripts\dev.ps1 train
```

Run tests:

```powershell
.\scripts\dev.ps1 test
```

## Running commands

Build only the JSON without execution:

```powershell
python -m python_agent.main "звук на 50" --no-log
```

Execute through C++ runtime:

```powershell
python -m python_agent.main "звук на 50" --execute
```

Run through helper script:

```powershell
.\scripts\dev.ps1 run "запусти блокнот" --execute
```

## Running UI

```powershell
.\scripts\dev.ps1 ui
```

The UI includes:

```text
command input
hotkey overlay
voice settings
application management
history
toast feedback
```

The default text hotkey is configurable in the Settings tab.

## Voice input

Voice input uses `faster-whisper`.

Default STT model directory:

```text
python_agent/models/stt/
```

This directory is ignored by Git because downloaded STT models can be large.

Voice modes:

```text
off
hotkey
continuous
```

Continuous voice mode can require the wake word:

```text
бивис
beavis
```

## Application indexing

Build local app index:

```powershell
.\scripts\dev.ps1 index
```

The app index is generated into:

```text
python_agent/data/cache/apps_index.json
```

This file is local runtime data and should not be committed.

User-added applications are stored locally under:

```text
python_agent/data/user_apps/
```

This folder is ignored by Git.

## Adding a user application

From UI or command line:

```powershell
python -m python_agent.training.add_user_app --path "D:\Tools\App\app.exe" --display-name "App" --speech-form "мой апп"
```

After adding applications, rebuild the index and retrain if needed:

```powershell
.\scripts\dev.ps1 index
.\scripts\dev.ps1 train
```

## C++ runtime

Python calls the C++ runtime through stdin/stdout JSON.

Expected executable paths:

```text
cpp_runtime/build/beavis_runtime.exe
cpp_runtime/build/Debug/beavis_runtime.exe
cpp_runtime/build/Release/beavis_runtime.exe
```

If `--execute` fails with `C++ runtime not found`, build the runtime:

```powershell
.\scripts\dev.ps1 build
```

## Logs

Runtime logs are written locally to:

```text
python_agent/data/logs/actions.jsonl
```

Logs are ignored by Git.

Logs are used for:

```text
debugging
dataset improvement
future retraining
unknown command analysis
```

## Troubleshooting

### Push fails because model file is too large

Do not commit generated models. See:

```text
docs/MODEL_STORAGE.md
```

### Command builds JSON but does not execute

Build C++ runtime:

```powershell
.\scripts\dev.ps1 build
```

### Application is not found

Rebuild app index:

```powershell
.\scripts\dev.ps1 index
```

### Window commands fail with missing arguments

Train local models:

```powershell
.\scripts\dev.ps1 train
```

### Voice model is slow or CUDA fails

Use CPU profile or check CUDA/ctranslate2 installation. STT models are stored locally in:

```text
python_agent/models/stt/
```

## Development rule

Do not mix NLU and execution.

Correct flow:

```text
Input
→ Python pipeline
→ ToolCall JSON
→ C++ Executor
→ Skill
→ SkillResult JSON
→ Logger
```

New skill checklist:

```text
1. Add dataset/generator if ML is needed.
2. Add argument extractor.
3. Add model wrapper if needed.
4. Register extractor in Python pipeline.
5. Add C++ skill.
6. Register C++ skill.
7. Add argument validation.
8. Add tests.
9. Update docs.
```
