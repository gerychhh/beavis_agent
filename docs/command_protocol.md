# Command Protocol — Beavis Agent

## 1. Purpose

This document defines the JSON protocol between the Python layer and the C++ runtime.

Python sends:

```text
ToolCall
```

C++ returns:

```text
SkillResult
```

The protocol is the execution contract. UI, voice, and text input must all eventually produce the same `ToolCall` structure.

## 2. ToolCall

A `ToolCall` represents one requested skill execution.

### Schema

```json
{
  "request_id": "cmd_12345678",
  "type": "tool_call",
  "skill": "volume_set",
  "args": {},
  "meta": {}
}
```

### Required fields

| Field | Type | Required | Description |
|---|---:|---:|---|
| `request_id` | string | yes | Unique command id |
| `type` | string | yes | Must be `tool_call` |
| `skill` | string | yes | Skill name |
| `args` | object | yes | Skill arguments |
| `meta` | object | no | Debug/tracing metadata |

### Recommended `meta`

```json
{
  "source": "text",
  "raw_text": "звук на 50",
  "normalized_text": "звук на 50",
  "skill_confidence": 0.94,
  "args_confidence": 0.95
}
```

Possible sources:

```text
text
voice
ui
test
```

## 3. SkillResult

A `SkillResult` represents the result of one skill execution.

### Success schema

```json
{
  "request_id": "cmd_12345678",
  "type": "skill_result",
  "success": true,
  "skill": "volume_set",
  "message": "Volume set to 50",
  "data": {
    "mode": "set",
    "percent": 50
  },
  "error": null
}
```

### Error schema

```json
{
  "request_id": "cmd_12345678",
  "type": "skill_result",
  "success": false,
  "skill": "open_app",
  "message": "Application was not resolved",
  "data": {},
  "error": {
    "code": "APP_NOT_FOUND",
    "details": "Cannot resolve app_id: unknown_app"
  }
}
```

### Fields

| Field | Type | Required | Description |
|---|---:|---:|---|
| `request_id` | string/null | yes | Original command id if available |
| `type` | string | yes | `skill_result` |
| `success` | boolean | yes | Execution status |
| `skill` | string/null | yes | Skill name if available |
| `message` | string | yes | Human-readable result |
| `data` | object | yes | Skill-specific result data |
| `error` | object/null | yes | Error details |

## 4. Skill: `volume_set`

### Purpose

Set or change system volume.

### Supported modes

```text
set
delta
```

### Set volume

```json
{
  "request_id": "cmd_001",
  "type": "tool_call",
  "skill": "volume_set",
  "args": {
    "mode": "set",
    "percent": 50
  }
}
```

Validation:

```text
mode must be "set"
percent must be integer
percent must be between 0 and 100
```

Legacy compatible form:

```json
{
  "request_id": "cmd_001",
  "type": "tool_call",
  "skill": "volume_set",
  "args": {
    "percent": 50
  }
}
```

### Change volume by delta

```json
{
  "request_id": "cmd_002",
  "type": "tool_call",
  "skill": "volume_set",
  "args": {
    "mode": "delta",
    "delta": -10
  }
}
```

Validation:

```text
mode must be "delta"
delta must be integer
delta must be between -100 and 100
```

## 5. Skill: `open_app`

### Purpose

Open or focus an installed application.

### Example

```json
{
  "request_id": "cmd_003",
  "type": "tool_call",
  "skill": "open_app",
  "args": {
    "app_id": "notepad"
  }
}
```

Validation:

```text
app_id must be a non-empty string
```

The C++ runtime resolves `app_id` through the app resolver.

## 6. Skill: `window_control`

### Purpose

Close, minimize, maximize, or restore a window.

### Supported actions

```text
close
minimize
maximize
restore
```

### Supported target types

```text
current
app
```

### Current window example

```json
{
  "request_id": "cmd_004",
  "type": "tool_call",
  "skill": "window_control",
  "args": {
    "action": "minimize",
    "target_type": "current"
  }
}
```

Validation:

```text
action must be supported
target_type must be "current"
```

### App window example

```json
{
  "request_id": "cmd_005",
  "type": "tool_call",
  "skill": "window_control",
  "args": {
    "action": "close",
    "target_type": "app",
    "app_id": "telegram"
  }
}
```

Validation:

```text
action must be supported
target_type must be "app"
app_id must be a non-empty string
```

## 7. Skill: `window_layout`

### Purpose

Move one or more windows to a layout on screen.

### Supported layouts

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

### One-window layout example

```json
{
  "request_id": "cmd_006",
  "type": "tool_call",
  "skill": "window_layout",
  "args": {
    "layout": "left_half",
    "targets": ["telegram"]
  }
}
```

### Two-window split example

```json
{
  "request_id": "cmd_007",
  "type": "tool_call",
  "skill": "window_layout",
  "args": {
    "layout": "split_2_vertical",
    "targets": ["telegram", "vscode"]
  }
}
```

### Four-window grid example

```json
{
  "request_id": "cmd_008",
  "type": "tool_call",
  "skill": "window_layout",
  "args": {
    "layout": "grid_2x2",
    "targets": ["telegram", "vscode", "chrome", "notepad"]
  }
}
```

Validation:

```text
layout must be supported
targets must be an array
targets must contain non-empty strings
left/right/top/bottom/center/fullscreen require at least 1 target
split_2_vertical and split_2_horizontal require at least 2 targets
grid_2x2 requires at least 4 targets
```

## 8. Error codes

Common validation/runtime error codes:

```text
INVALID_JSON
INVALID_TYPE
INVALID_ARGS
MISSING_ARG
UNKNOWN_SKILL
SKILL_FAILED
INTERNAL_ERROR
```

Skill-specific errors may include:

```text
APP_NOT_FOUND
FILE_NOT_FOUND
PATH_NOT_FOUND
ACCESS_DENIED
WINDOW_NOT_FOUND
WINDOW_FOCUS_FAILED
SHELL_EXECUTE_FAILED
```

## 9. Protocol rules

### Rule 1 — C++ only executes validated ToolCalls

The C++ runtime must not execute invalid JSON or invalid arguments.

### Rule 2 — Python must not bypass the protocol

UI, voice, tests, and text input must all go through:

```text
ToolCall JSON → C++ runtime
```

### Rule 3 — New skills must update this file

Every new skill must define:

```text
skill name
purpose
arguments
validation
examples
result data
```

### Rule 4 — Keep backward compatibility when possible

If an old argument format is supported, document it explicitly.

Example:

```json
{
  "skill": "volume_set",
  "args": {
    "percent": 80
  }
}
```

is accepted as legacy `mode = set`.

## 10. Example full flow

Input:

```text
звук на 50
```

Python output:

```json
{
  "request_id": "cmd_ab12cd34",
  "type": "tool_call",
  "skill": "volume_set",
  "args": {
    "mode": "set",
    "percent": 50
  },
  "meta": {
    "source": "text",
    "raw_text": "звук на 50",
    "normalized_text": "звук на 50",
    "skill_confidence": 0.94,
    "args_confidence": 0.95
  }
}
```

C++ output:

```json
{
  "request_id": "cmd_ab12cd34",
  "type": "skill_result",
  "success": true,
  "skill": "volume_set",
  "message": "Volume set to 50",
  "data": {
    "mode": "set",
    "previous_percent": 80,
    "percent": 50
  },
  "error": null
}
```
