# Command Protocol

This document defines the JSON protocol between `python_agent` and `cpp_runtime`.

For the first MVP, Python sends one `ToolCall` to C++ and C++ returns one
`SkillResult`.

```text
Text input
-> Python NLU pipeline
-> ToolCall JSON
-> C++ Executor
-> C++ Skill
-> SkillResult JSON
-> Python Logger
```

## Goals

- Keep command understanding separate from command execution.
- Use strict JSON as the only boundary between Python and C++.
- Make the protocol stable before adding real Windows actions.
- Allow future message types without breaking the MVP.

## Current Message Types

The MVP uses only:

```text
tool_call
skill_result
```

Future versions may add:

```text
plan
plan_result
clarification
unknown_command
```

## ToolCall

`ToolCall` is a request to execute one skill.

### Required Fields

```text
request_id
type
skill
args
```

### Optional Fields

```text
meta
```

### Schema

```json
{
  "request_id": "string",
  "type": "tool_call",
  "skill": "string",
  "args": {},
  "meta": {}
}
```

### Example

```json
{
  "request_id": "cmd_001",
  "type": "tool_call",
  "skill": "volume_set",
  "args": {
    "mode": "set",
    "percent": 80
  },
  "meta": {
    "source": "text",
    "raw_text": "сделай громкость на 80",
    "normalized_text": "сделай громкость на 80",
    "skill_confidence": 0.95,
    "args_confidence": 0.93
  }
}
```

## SkillResult

`SkillResult` is the result of executing one skill.

### Required Fields

```text
request_id
type
success
skill
message
data
error
```

### Schema

```json
{
  "request_id": "string",
  "type": "skill_result",
  "success": true,
  "skill": "string",
  "message": "string",
  "data": {},
  "error": null
}
```

### Success Example

```json
{
  "request_id": "cmd_001",
  "type": "skill_result",
  "success": true,
  "skill": "volume_set",
  "message": "Volume set to 80",
  "data": {
    "mode": "set",
    "percent": 80
  },
  "error": null
}
```

### Error Example

```json
{
  "request_id": "cmd_003",
  "type": "skill_result",
  "success": false,
  "skill": "open_app",
  "message": "Application not found",
  "data": {},
  "error": {
    "code": "APP_NOT_FOUND",
    "details": "No existing launch target for app_id: unknown_app"
  }
}
```

## Skill Arguments

### volume_set

Sets system volume or changes it relative to the current volume.

```json
{
  "skill": "volume_set",
  "args": {
    "mode": "set",
    "percent": 100
  }
}
```

```json
{
  "skill": "volume_set",
  "args": {
    "mode": "delta",
    "delta": -20
  }
}
```

Rules:

- `mode` is required.
- `mode` must be `set` or `delta`.
- If `mode` is `set`, `percent` is required.
- `percent` must be an integer between `0` and `100`.
- If `mode` is `delta`, `delta` is required.
- `delta` must be an integer between `-100` and `100`.

### open_app

Makes an application visible.

```json
{
  "skill": "open_app",
  "args": {
    "app_id": "chrome"
  }
}
```

Rules:

- `app_id` is required.
- `app_id` must be a non-empty string.
- Python models choose the canonical `app_id`.
- C++ `OpenAppSkill` resolves `app_id` through `apps_index.json`.
- If a matching top-level window is already open, C++ focuses that window instead of launching a new process.
- If no matching window is found, C++ launches the resolved target.

Existing window result:

```json
{
  "success": true,
  "skill": "open_app",
  "message": "Application focused: chrome",
  "data": {
    "app_id": "chrome",
    "focused_existing": true,
    "launched": false
  },
  "error": null
}
```

New launch result:

```json
{
  "success": true,
  "skill": "open_app",
  "message": "Application opened: chrome",
  "data": {
    "app_id": "chrome",
    "focused_existing": false,
    "launched": true
  },
  "error": null
}
```

### window_control

Controls an existing visible window.

```json
{
  "skill": "window_control",
  "args": {
    "action": "minimize",
    "target_type": "current"
  }
}
```

```json
{
  "skill": "window_control",
  "args": {
    "action": "close",
    "target_type": "app",
    "app_id": "notepad"
  }
}
```

Rules:

- `action` is required.
- `action` must be one of:

```text
close
minimize
maximize
restore
```

- `target_type` is required.
- `target_type` must be `current` or `app`.
- If `target_type` is `app`, `app_id` is required.
- C++ finds the matching visible window and applies `ShowWindow` or `WM_CLOSE`.

### window_layout

Arranges one or more existing visible windows on the screen.

Single-window placement:

```json
{
  "skill": "window_layout",
  "args": {
    "layout": "left_half",
    "targets": ["current"]
  }
}
```

Two-window split:

```json
{
  "skill": "window_layout",
  "args": {
    "layout": "split_2_vertical",
    "targets": ["telegram", "vscode"]
  }
}
```

Rules:

- `layout` is required.
- `layout` must be one of:

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

- `targets` is required and must be a non-empty array of app ids.
- `current` means the active foreground window.
- Single-window layouts require at least one target.
- `split_2_vertical` and `split_2_horizontal` require at least two targets.
- `grid_2x2` requires at least four targets.
- C++ finds already-open windows. It does not launch missing applications for this skill.

### window_snap

Moves or resizes an application window.

```json
{
  "skill": "window_snap",
  "args": {
    "app_query": "браузер",
    "position": "left"
  }
}
```

Rules:

- `position` is required.
- `position` must be one of:

```text
left
right
maximize
minimize
```

- `app_query` is optional only when the active window should be used.

## Error Codes

The C++ executor should return `success: false` and an `error` object when it
cannot execute a command.

Recommended MVP error codes:

```text
INVALID_JSON
INVALID_TYPE
UNKNOWN_SKILL
INVALID_ARGS
MISSING_ARG
APP_NOT_FOUND
WINDOW_NOT_FOUND
WINDOW_ACTION_FAILED
SKILL_FAILED
INTERNAL_ERROR
```

### INVALID_JSON

Returned when stdin does not contain valid JSON.

```json
{
  "request_id": null,
  "type": "skill_result",
  "success": false,
  "skill": null,
  "message": "Invalid JSON",
  "data": {},
  "error": {
    "code": "INVALID_JSON",
    "details": "Failed to parse input"
  }
}
```

### UNKNOWN_SKILL

Returned when the requested skill is not registered in `SkillRegistry`.

```json
{
  "request_id": "cmd_010",
  "type": "skill_result",
  "success": false,
  "skill": "unknown_skill",
  "message": "Unknown skill",
  "data": {},
  "error": {
    "code": "UNKNOWN_SKILL",
    "details": "Skill is not registered"
  }
}
```

## Transport

For the MVP, `cpp_runtime` is a process called by Python through `subprocess`.

Python sends one JSON object through stdin.

C++ returns one JSON object through stdout.

Stderr may be used only for debug messages. Python should parse stdout as JSON.

```text
python_agent/cpp_client.py
-> subprocess
-> cpp_runtime executable
-> stdin: ToolCall JSON
-> stdout: SkillResult JSON
```

Future transports may include:

```text
persistent process
named pipes
local HTTP
full C++ runtime
```

The JSON payloads should stay compatible across transports.

## Compatibility Rules

- `type` must always be present.
- Unknown top-level fields should be ignored by receivers.
- Required fields must never be silently guessed by C++.
- Python may include `meta`; C++ may ignore it.
- `request_id` must be copied from `ToolCall` to `SkillResult`.
- All C++ results must be valid JSON.
- All command execution must go through `SkillRegistry` and `Executor`.
- Real Windows actions should be added only after fake skills work end to end.

## MVP End-To-End Example

Input text:

```text
звук на полную
```

Python builds:

```json
{
  "request_id": "cmd_001",
  "type": "tool_call",
  "skill": "volume_set",
  "args": {
    "mode": "set",
    "percent": 100
  },
  "meta": {
    "source": "text",
    "raw_text": "звук на полную",
    "normalized_text": "звук на полную",
    "skill_confidence": 0.94,
    "args_confidence": 0.95
  }
}
```

C++ returns:

```json
{
  "request_id": "cmd_001",
  "type": "skill_result",
  "success": true,
  "skill": "volume_set",
  "message": "Volume set to 100",
  "data": {
    "mode": "set",
    "percent": 100
  },
  "error": null
}
```

Python logs the command to:

```text
python_agent/data/logs/actions.jsonl
```
