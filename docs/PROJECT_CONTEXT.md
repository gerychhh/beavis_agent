# Project Context

Beavis Agent is built for imperfect user input. Users may write with typos,
mix languages, use wake words, or omit polite structure. The project should keep
that strength while making the code easier to extend.

## Product Goal

```text
Imperfect command
-> stable intent and arguments
-> strict ToolCall JSON
-> validated Windows action
```

Example:

```text
bavis сделай справо codex
```

Expected internal command:

```json
{
  "skill": "window_layout",
  "args": {
    "layout": "right_half",
    "targets": ["codex"]
  }
}
```

## Non-Negotiable Boundaries

```text
Python understands commands.
C++ executes Windows actions.
JSON is the only execution contract.
UI is not an execution layer.
Voice is not an execution layer.
```

## Current Skills

```text
open_app
volume_set
window_control
window_layout
```

Do not add new skills during the simplification pass. First keep the existing
ones modular and stable.

## Current Refactor Direction

The current cleanup is not a rewrite. It introduces clearer ownership:

```text
CommandPipeline     understands text and returns CommandDecision
CommandExecutor     executes ready ToolCall objects through CppClient
SkillRegistry       owns skill specs and extractors
ActionLogger        records output and execution result
```

Compatibility files stay in place until callers are migrated.

## Model Policy

ML behavior is part of the product. Do not replace tolerant models with narrow
regex-only logic just because a command looks easy. Rules are useful for small
structured details, but the system must keep handling messy user phrasing.

Generated model files stay local and ignored.

## Definition Of Done

```text
Python compiles.
Golden commands pass.
Model tests pass their thresholds.
C++ runtime builds.
Smoke commands build ToolCall JSON.
Desktop UI builds.
Docs describe the actual code.
.gitignore keeps generated artifacts out.
```
