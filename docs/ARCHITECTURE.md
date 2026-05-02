# Architecture — Beavis Agent

## 1. Overview

Beavis Agent is split into two main layers:

```text
Python layer — understanding, UI, voice, training
C++ layer    — validation and Windows execution
```

The boundary between the two layers is JSON.

```text
Python sends ToolCall JSON.
C++ returns SkillResult JSON.
```

## 2. System diagram

```text
┌────────────────────┐
│ Text input          │
│ Voice input         │
│ UI overlay          │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ Python pipeline     │
│ - Normalizer        │
│ - Skill classifier  │
│ - Arg extractor     │
└─────────┬──────────┘
          │ ToolCall JSON
          ▼
┌────────────────────┐
│ CppClient           │
│ subprocess stdin    │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ C++ runtime         │
│ - Executor          │
│ - ArgsValidator     │
│ - SkillRegistry     │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ Windows skills      │
│ - open_app          │
│ - volume_set        │
│ - window_control    │
│ - window_layout     │
└─────────┬──────────┘
          │ SkillResult JSON
          ▼
┌────────────────────┐
│ Python logger       │
└────────────────────┘
```

## 3. Python layer

### 3.1 Normalizer

The normalizer prepares the text for models and rules.

Responsibilities:

```text
lowercase
ё → е
punctuation cleanup
filler word removal
simple lexical replacements
space cleanup
```

Not responsible for:

```text
choosing skill
extracting arguments
executing commands
making skill-specific semantic replacements
```

### 3.2 Skill classifier

Input:

```text
normalized text
```

Output:

```json
{
  "skill": "volume_set",
  "confidence": 0.94,
  "source": "model_joblib"
}
```

Allowed skills:

```text
open_app
volume_set
window_control
window_layout
unknown
```

If the model is missing or disabled, the classifier may fall back to rule-based classification.

### 3.3 Argument extractors

Each skill has its own extractor.

Reason:

```text
Different skills have different argument schemas.
```

Examples:

```text
volume_set      → mode, percent/delta
open_app        → app_id
window_control  → action, target_type, app_id
window_layout   → layout, targets
```

Output:

```json
{
  "args": {},
  "confidence": 0.0,
  "missing": ["app_id"],
  "source": "model_missing"
}
```

If `missing` is not empty, the pipeline should not execute the command.

### 3.4 App resolver/indexer

The app resolver maps user/app names to stable `app_id` values.

Sources:

```text
system apps
Windows App Paths
Start Menu shortcuts
Windows apps
manual config
user-added apps
```

Generated index:

```text
python_agent/data/cache/apps_index.json
```

The index is local runtime data and is ignored by Git.

### 3.5 Voice layer

Voice flow:

```text
microphone
→ record until silence
→ faster-whisper
→ transcript
→ optional wake-word removal
→ Python pipeline
```

Voice modes:

```text
off
hotkey
continuous
```

Voice models are stored locally in:

```text
python_agent/models/stt/
```

This folder is ignored by Git.

### 3.6 UI layer

The UI is implemented with PySide6.

Responsibilities:

```text
main window
settings
text command input
hotkey overlay
voice overlay
toast feedback
history
user application management
```

The UI does not directly execute Windows actions. It sends commands to the same pipeline.

## 4. C++ layer

### 4.1 CppClient

Python starts the C++ executable and communicates through stdin/stdout.

Expected executable locations:

```text
cpp_runtime/build/beavis_runtime.exe
cpp_runtime/build/Debug/beavis_runtime.exe
cpp_runtime/build/Release/beavis_runtime.exe
```

### 4.2 Executor

Executor responsibilities:

```text
parse ToolCall JSON
validate required top-level fields
check message type
find skill in SkillRegistry
validate skill arguments
execute skill
return SkillResult JSON
```

### 4.3 ArgsValidator

ArgsValidator checks skill-specific argument schema before execution.

Validation examples:

```text
volume_set.percent must be integer 0..100
volume_set.delta must be integer -100..100
open_app.app_id must be non-empty string
window_control.action must be supported
window_layout.targets must contain enough items
```

### 4.4 SkillRegistry

SkillRegistry maps skill names to C++ skill objects.

Current registered skills:

```text
open_app
volume_set
window_control
window_layout
```

### 4.5 Skills

Skills perform Windows actions.

Current skills:

```text
OpenAppSkill
VolumeSetSkill
WindowControlSkill
WindowLayoutSkill
```

## 5. JSON boundary

Python and C++ must not share Python objects or C++ objects directly.

Correct boundary:

```text
ToolCall JSON → C++ → SkillResult JSON
```

This allows future replacement of subprocess with:

```text
persistent runtime
named pipes
local HTTP
IPC protocol
```

without changing the command protocol.

## 6. Model lifecycle

Correct lifecycle:

```text
generate dataset
train model
evaluate model
save local .joblib
run tests
use in pipeline
```

Generated models should not be committed.

Reasons:

```text
model files can exceed GitHub limits
model files are generated artifacts
models depend on Python/sklearn versions
models can be recreated locally
```

## 7. Local data lifecycle

Ignored local data:

```text
python_agent/data/cache/
python_agent/data/logs/
python_agent/data/settings/
python_agent/data/user_apps/
external_data/
```

These files may contain:

```text
machine-specific paths
user commands
local settings
generated app indexes
runtime logs
```

## 8. Adding a new skill

Checklist:

```text
1. Define the skill name.
2. Define argument schema.
3. Add examples and dataset generator if needed.
4. Add Python argument extractor.
5. Register extractor in CommandPipeline.
6. Add C++ skill class.
7. Register C++ skill in main.cpp.
8. Add validation in ArgsValidator.
9. Add tests.
10. Update COMMAND_PROTOCOL.md.
11. Update README.md if user-facing.
```

## 9. Design rules

Do not:

```text
execute Windows actions from UI
execute skills directly from voice layer
put skill-specific logic into global normalizer
let C++ do ML classification
return unvalidated JSON to execution
commit local runtime files
commit generated models
```

Do:

```text
keep one command protocol
validate before execution
log every command result
train models from reproducible datasets
keep C++ as execution boundary
keep Python as understanding/training/UI layer
```
