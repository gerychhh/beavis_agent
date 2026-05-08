# Command Protocol

This document defines the JSON contract between Python and the C++ runtime.

Python sends `ToolCall`. C++ returns `SkillResult`.

## CommandDecision

`CommandDecision` is the Python-side understanding result. It is not sent to the
C++ runtime.

```json
{
  "status": "ready",
  "raw_text": "сверни телеграм",
  "normalized_text": "сверни телеграм",
  "tool_call": {
    "request_id": "cmd_12345678",
    "type": "tool_call",
    "skill": "window_control",
    "args": {
      "action": "minimize",
      "target_type": "app",
      "app_id": "telegram"
    }
  },
  "reason": null,
  "question": null,
  "debug": {}
}
```

Statuses:

```text
ready                 ToolCall is ready
rejected              command is unknown or unsafe to build
needs_clarification   skill is plausible, but required args are missing
error                 classifier/extractor/system error
```

## ToolCall

`ToolCall` is the execution request.

```json
{
  "request_id": "cmd_12345678",
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

Required fields:

| Field | Type | Required |
|---|---|---|
| `request_id` | string | yes |
| `type` | string, must be `tool_call` | yes |
| `skill` | string | yes |
| `args` | object | yes |
| `meta` | object | no |

## SkillResult

`SkillResult` is the execution response.

```json
{
  "request_id": "cmd_12345678",
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

Error shape:

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

## Skills

### `open_app`

```json
{
  "skill": "open_app",
  "args": {
    "app_id": "google_chrome"
  }
}
```

Validation:

```text
app_id must be a non-empty string
```

### `volume_set`

Set absolute volume:

```json
{
  "skill": "volume_set",
  "args": {
    "mode": "set",
    "percent": 50
  }
}
```

Change volume by delta:

```json
{
  "skill": "volume_set",
  "args": {
    "mode": "delta",
    "delta": -10
  }
}
```

Validation:

```text
mode must be set or delta
percent must be integer 0..100 when mode is set
delta must be integer -100..100 when mode is delta
```

Legacy compatible form:

```json
{
  "skill": "volume_set",
  "args": {
    "percent": 50
  }
}
```

### `window_control`

Current window:

```json
{
  "skill": "window_control",
  "args": {
    "action": "close",
    "target_type": "current"
  }
}
```

App window:

```json
{
  "skill": "window_control",
  "args": {
    "action": "minimize",
    "target_type": "app",
    "app_id": "telegram"
  }
}
```

Supported actions:

```text
close
minimize
maximize
restore
```

### `window_layout`

```json
{
  "skill": "window_layout",
  "args": {
    "layout": "split_2_vertical",
    "targets": ["telegram", "codex"]
  }
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

## Rules

```text
C++ executes only validated ToolCalls.
UI and voice must not bypass Python CommandPipeline.
Python must not bypass C++ for Windows actions.
Every new skill must update this file.
Backward-compatible argument forms must be documented.
```
