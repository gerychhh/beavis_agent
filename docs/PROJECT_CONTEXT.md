# Project Context — Beavis Agent

## 1. Project name

```text
Beavis Agent
```

Beavis Agent is a local Windows desktop assistant with text and voice input.

The project goal is to convert imperfect user commands into strict JSON actions and execute them through a controlled C++ runtime.

## 2. Main idea

The user should not be required to write or speak commands perfectly.

Example user input:

```text
брух сделай музон на полную
```

Expected internal result:

```json
{
  "request_id": "cmd_xxxxxxxx",
  "type": "tool_call",
  "skill": "volume_set",
  "args": {
    "mode": "set",
    "percent": 100
  },
  "meta": {
    "source": "text",
    "raw_text": "брух сделай музон на полную",
    "normalized_text": "сделай музыка на полную",
    "skill_confidence": 0.94,
    "args_confidence": 0.95
  }
}
```

The C++ runtime receives the JSON, validates arguments, executes the skill, and returns a JSON result.

## 3. Current implementation

The current implementation is not just a minimal fake MVP anymore.

It includes:

```text
Python command pipeline
ML skill classifier
ML argument extractors
application resolver/indexer
Tauri desktop UI
global hotkeys
voice input through faster-whisper
C++ runtime
real Windows actions
logging
developer script scripts/dev.ps1
```

Current supported skills:

```text
open_app
volume_set
window_control
window_layout
```

## 4. High-level pipeline

```text
Text input
→ Normalizer
→ Skill classifier
→ Skill-specific argument extractor
→ ToolCall JSON
→ CppClient
→ C++ Executor
→ ArgsValidator
→ SkillRegistry
→ C++ Skill
→ SkillResult JSON
→ ActionLogger
```

Voice input uses the same pipeline after transcription:

```text
Microphone
→ VAD / recording
→ faster-whisper transcription
→ optional wake-word stripping
→ same Python pipeline
→ C++ runtime
```

## 5. Python responsibilities

Python handles:

```text
text normalization
skill classification
argument extraction
dataset generation
model training
model loading
application index generation
UI API bridge
voice transcription
voice settings
logs
developer workflow
```

Python should not be the final place where system actions are executed.

The final execution boundary is the C++ runtime.

## 6. C++ responsibilities

C++ handles:

```text
JSON parsing
ToolCall validation
SkillRegistry
safe skill dispatch
Windows API execution
application launching
volume control
window control
window layout
SkillResult output
```

The C++ runtime accepts JSON through stdin and returns JSON through stdout.

## 7. Why cascade architecture is used

The project should not use one giant model that directly returns full JSON.

Correct architecture:

```text
text → skill classifier → selected skill
text + selected skill → argument extractor
args → validator
ToolCall → executor
```

Reason:

```text
Different skills need different arguments.
Each argument extractor can be trained and tested separately.
Skill classification and slot extraction have different failure modes.
It is easier to add new skills without rewriting the whole system.
```

## 8. Current skills

### open_app

Purpose:

```text
Open or focus an installed application.
```

Arguments:

```json
{
  "app_id": "notepad"
}
```

Examples:

```text
запусти блокнот
открой телеграм
вруби браузер
```

### volume_set

Purpose:

```text
Set or change system volume.
```

Set mode:

```json
{
  "mode": "set",
  "percent": 50
}
```

Delta mode:

```json
{
  "mode": "delta",
  "delta": -10
}
```

Examples:

```text
звук на 50
громкость на полную
сделай потише
```

### window_control

Purpose:

```text
Close, minimize, maximize, or restore current/app window.
```

Current window example:

```json
{
  "action": "minimize",
  "target_type": "current"
}
```

Application window example:

```json
{
  "action": "close",
  "target_type": "app",
  "app_id": "telegram"
}
```

Supported actions:

```text
close
minimize
maximize
restore
```

### window_layout

Purpose:

```text
Place one or several windows on screen.
```

Example:

```json
{
  "layout": "split_2_vertical",
  "targets": ["telegram", "vscode"]
}
```

Supported layouts:

```text
left_half
right_half
top_half
bottom_half
center
fullscreen
split_2_vertical
split_2_horizontal
grid_2x2
```

## 9. Model policy

Generated model files should not be committed.

Ignored paths:

```text
python_agent/models/*
python_agent/models/stt/*
```

Kept placeholders:

```text
python_agent/models/.gitkeep
python_agent/models/stt/.gitkeep
```

Reason:

```text
Models can be large.
GitHub blocks files over 100 MiB.
Joblib model compatibility depends on dependency versions.
The project should be reproducible through training scripts.
```

The correct model workflow is:

```text
clone repo
install dependencies
run training
models are generated locally
run tests
run app
```

## 10. Local runtime data policy

The following are local runtime artifacts and should not be committed:

```text
python_agent/data/cache/
python_agent/data/logs/
python_agent/data/settings/
python_agent/data/user_apps/
external_data/
```

Reason:

```text
They are machine-specific.
They may contain personal app paths.
They may contain user commands.
They may change constantly.
```

## 11. Developer workflow

Main helper script:

```powershell
.\scripts\dev.ps1
```

Common workflow:

```powershell
.\scripts\dev.ps1 setup
.\scripts\dev.ps1 build
.\scripts\dev.ps1 index
.\scripts\dev.ps1 train
.\scripts\dev.ps1 test
.\scripts\dev.ps1 smoke
.\scripts\dev.ps1 ui-dev
```

First run:

```powershell
.\scripts\dev.ps1 all
```

## 12. Important architectural rules

Do not do this:

```text
UI directly calls Windows API.
Voice layer directly executes skills.
Python finalizes Windows actions directly.
A skill calls another skill without Executor.
Normalizer performs skill-specific semantic decisions.
One global model returns every possible JSON field.
```

Do this:

```text
Input
→ Python understanding
→ strict ToolCall JSON
→ C++ validation
→ C++ execution
→ strict SkillResult JSON
→ logging
```

## 13. Normalizer rules

Normalizer may do:

```text
lowercase
replace ё with е
remove punctuation
remove filler words
replace obvious lexical slang
collapse spaces
```

Normalizer should not do skill-specific logic.

Do not put this into global normalizer:

```text
на полную → 100
слева → left_half
закрой → close
```

Those meanings belong to skill-specific extractors.

## 14. Logging

Each successful pipeline build is logged to:

```text
python_agent/data/logs/actions.jsonl
```

Logs contain:

```text
raw text
normalized text
predicted skill
predicted arguments
confidence values
ToolCall
execution result
training status
```

Logs are candidates for future learning loops.

## 15. Future expansion

Possible future layers:

```text
planner fallback for multi-step commands
custom command macros
persistent C++ runtime
named pipes instead of subprocess
speaker recognition
wake-word model
command sharing hub
automatic log review
model evaluation dashboard
installer
```

The current architecture should allow these additions without rewriting the core protocol.

## 16. Definition of Done for current stable state

A stable local development state means:

```text
1. Python dependencies install successfully.
2. C++ runtime builds successfully.
3. App index is generated.
4. Required local ML models are trained.
5. Smoke tests pass.
6. Text commands produce valid ToolCall JSON.
7. --execute commands return SkillResult JSON.
8. UI starts.
9. Models and runtime data are not tracked by Git.
10. README and docs match the actual codebase.
```
