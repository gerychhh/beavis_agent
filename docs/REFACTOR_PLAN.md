# Refactor Plan

Goal: simplify the project without adding a planner and without rewriting the
working app.

## Keep

```text
Python = command understanding
C++ = Windows execution
JSON = contract
UI = interface
```

Keep current skills:

```text
open_app
volume_set
window_control
window_layout
```

## Current Completed Direction

```text
CommandDecision introduced
CommandExecutor introduced
SkillSpec and SkillRegistry introduced
Golden command tests introduced
Core pipeline compatibility wrapper kept
Skill module folders started
```

## Next Safe Steps

```text
1. Move extractor implementations into python_agent/skills one skill at a time.
2. Keep nlu/argument_extractors wrappers until imports are gone.
3. Add RejectionPolicy without changing successful current commands.
4. Create ui_bridge beside old bridge, then migrate stdio_server.
5. Split UI only by moving code, not redesigning it.
6. Extract C++ Windows helpers gradually after tests are green.
7. Add training CLI after skill examples are stable.
```

## Do Not Do

```text
Do not rewrite from scratch.
Do not move Windows API into Python.
Do not move ML/NLU into C++.
Do not add new skills during this cleanup.
Do not replace tolerant ML behavior with narrow rules.
Do not change UI design while splitting files.
Do not break ToolCall or SkillResult JSON.
```
