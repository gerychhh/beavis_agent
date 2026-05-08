# Architecture

Beavis Agent is intentionally split into understanding, transport, and execution
layers.

```text
Input Layer
  CLI
  Tauri UI
  Voice

API Layer
  Python API services
  JSON-lines bridge

Command Layer
  CommandPipeline
  CommandDecision
  CommandExecutor
  ActionLogger

NLU Layer
  Normalizer
  SkillClassifier
  SkillRegistry
  Skill-specific extractors

Execution Layer
  CppClient
  C++ runtime
  ArgsValidator
  C++ skills

Feedback Layer
  Logs
  History
  Training data
```

## Core Flow

```text
raw text
-> normalize
-> classify skill
-> select SkillSpec from SkillRegistry
-> run that skill's extractor
-> build CommandDecision
-> build ToolCall if ready
-> execute through C++ only when requested
-> log result
```

`CommandPipeline` does not execute Windows actions. `CommandExecutor` does not
understand text. `ActionLogger` does not make decisions.

## Python Responsibilities

Python owns:

```text
text normalization
skill classification
argument extraction
ToolCall construction
voice transcription
UI API bridge
training scripts
local app indexing
logs and history
```

Python must not be the final execution layer for Windows actions.

## C++ Responsibilities

C++ owns:

```text
JSON parsing for execution
argument validation
skill dispatch
Windows API calls
application launching
volume control
window control
window layout
SkillResult output
```

The C++ runtime is the final safety boundary before the Windows API.

## JSON Boundary

Python and C++ communicate through JSON only:

```text
ToolCall JSON -> C++ runtime -> SkillResult JSON
```

This keeps UI, voice, CLI, and future transports on the same contract.

## Python Core Files

```text
python_agent/core/schemas.py            ToolCall, SkillResult, predictions
python_agent/core/decision.py           CommandDecision
python_agent/core/command_pipeline.py   NLU-to-ToolCall pipeline
python_agent/core/command_executor.py   ToolCall-to-C++ execution
python_agent/core/pipeline.py           Compatibility wrapper
python_agent/core/logger.py             ActionLogger
```

## Skill Registry

Skill metadata lives under `python_agent/skills/`.

```text
python_agent/skills/spec.py
python_agent/skills/registry.py
python_agent/skills/open_app/
python_agent/skills/volume_set/
python_agent/skills/window_control/
python_agent/skills/window_layout/
```

The old `python_agent/nlu/argument_extractors/` modules remain as compatibility
entrypoints while skill logic is moved gradually into `python_agent/skills/`.

## UI Boundary

The desktop UI talks to Python through the bridge:

```text
desktop_ui
-> Tauri Rust bridge
-> python_agent/bridge/stdio_server.py
-> python_agent/bridge/router.py
-> python_agent/api/*
```

The UI must not call Windows APIs directly.

## Voice Boundary

Voice produces text, then enters the same command path:

```text
microphone
-> VAD / capture
-> faster-whisper
-> wake-word cleanup
-> CommandPipeline
```

Voice code must not execute skills directly.

## Local Data

Generated and local data is ignored:

```text
python_agent/data/cache/
python_agent/data/logs/
python_agent/data/settings/
python_agent/data/user_apps/
python_agent/models/
external_data/
```

These files are machine-specific, private, or reproducible artifacts.
