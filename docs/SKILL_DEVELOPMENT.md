# Skill Development

This project should make adding a skill predictable. A new skill must be a
module with a clear Python contract, a C++ executor, validation, examples, and
tests.

Do not add Planner or multi-step planning as part of a normal skill.

## Current Skills

```text
open_app
volume_set
window_control
window_layout
```

## Skill Module Layout

Python skill modules live under `python_agent/skills/`:

```text
python_agent/skills/<skill_name>/
  __init__.py
  spec.py
  extractor.py
  examples.py
```

The legacy extractor package may remain as a compatibility entrypoint:

```text
python_agent/nlu/argument_extractors/<skill_name>.py
```

Do not remove a legacy import until all callers have moved.

## Python Contract

Each skill exposes `SPEC` from `spec.py`.

```python
from python_agent.skills.spec import ArgSpec, SkillSpec
from python_agent.skills.new_skill.extractor import NewSkillExtractor
from python_agent.skills.new_skill.examples import EXAMPLES

SPEC = SkillSpec(
    name="new_skill",
    description="Short human-readable purpose",
    risk="low",
    extractor=NewSkillExtractor(),
    args=[
        ArgSpec(name="mode", type="enum", values=["set", "delta"]),
        ArgSpec(
            name="percent",
            type="int",
            required=False,
            min_value=0,
            max_value=100,
            required_if={"mode": "set"},
        ),
    ],
    examples=EXAMPLES,
    enabled=True,
)
```

Fields:

```text
name          stable skill id used in ToolCall.skill
description   short developer-facing description
risk          low / medium / high, used for documentation and review
extractor     object that returns ArgsPrediction
args          argument schema for docs and future validation helpers
examples      small representative examples for docs/training/golden seeds
enabled       false disables registration without deleting code
```

Use `required_if` only for simple conditional requirements. C++
`ArgsValidator` remains the final execution guard.

## Extractor Contract

An extractor receives normalized text and returns `ArgsPrediction`.

```python
from python_agent.core.schemas import ArgsPrediction

class NewSkillExtractor:
    def extract(self, text: str) -> ArgsPrediction:
        return ArgsPrediction(
            args={"app_id": "telegram"},
            confidence=0.91,
            missing=[],
            source="model_joblib",
        )
```

Rules:

```text
Return missing=[...] for normal NLU uncertainty.
Raise only for actual system/programmer errors.
Keep tolerant ML behavior when users commonly write messy commands.
Use rules/regex for simple structured details only when they are robust.
```

## Python Registration

Add the skill spec to `python_agent/skills/registry.py`:

```python
from python_agent.skills.new_skill.spec import SPEC as NEW_SKILL

for spec in (OPEN_APP, VOLUME_SET, WINDOW_CONTROL, WINDOW_LAYOUT, NEW_SKILL):
    ...
```

`CommandPipeline` must discover extractors through `SkillRegistry`; it should
not import concrete skill extractor classes.

## Golden Cases

Add behavior examples to:

```text
python_agent/data/eval/golden_commands.jsonl
```

Ready case:

```json
{"text":"пример команды","status":"ready","skill":"new_skill","args":{"mode":"set"}}
```

Rejected case:

```json
{"text":"неизвестная просьба","status":"rejected","reason":"unknown_command"}
```

Missing-args case:

```json
{"text":"сверни","status":"needs_clarification","reason":"missing_args","question_contains":"Missing required arguments"}
```

Run:

```powershell
python python_agent\training\test_golden_commands.py
```

Golden tests should lock current expected behavior. Do not add idealized cases
that fail in the current runner unless the implementation is changed in the same
commit.

## C++ Contract

Every executable skill needs C++ support:

```text
cpp_runtime/src/skills/<category>/NewSkill.h
cpp_runtime/src/skills/<category>/NewSkill.cpp
cpp_runtime/src/executor/ArgsValidator.cpp
cpp_runtime/src/executor/SkillRegistry.cpp
cpp_runtime/CMakeLists.txt
```

C++ responsibilities:

```text
parse args
validate args before Windows API calls
execute the Windows action
return SkillResult JSON
never ask Python or UI to perform Windows actions
```

Update `docs/COMMAND_PROTOCOL.md` with the new `ToolCall.args` shape and
possible `SkillResult.error.code` values.

## Training

If the skill uses ML:

```text
add or update dataset source
add generator script if needed
add train script if needed
add model test with a clear threshold
document model path in MODEL_STORAGE.md
```

Generated models stay local and ignored. Do not commit `.joblib` files unless
the project policy changes.

## UI/API

Most new skills do not need UI changes. The command path is generic:

```text
UI text input
-> commands.build_decision / commands.run
-> CommandPipeline
-> ToolCall
-> C++ runtime
```

Only update UI when the skill needs a dedicated page, settings, or visible
status.

## Checklist

```text
1. Create python_agent/skills/<skill_name>/.
2. Add examples.py.
3. Add extractor.py.
4. Add spec.py with SkillSpec.
5. Register SPEC in python_agent/skills/registry.py.
6. Keep or add compatibility wrapper under nlu/argument_extractors if needed.
7. Add golden cases for ready/rejected/needs_clarification where relevant.
8. Add C++ skill implementation.
9. Add C++ ArgsValidator rules.
10. Register the C++ skill and update CMakeLists if new files were added.
11. Update COMMAND_PROTOCOL.md.
12. Update README/docs if the skill is user-facing.
13. Run Python tests, smoke, C++ build, and UI build.
```

Verification:

```powershell
python -m compileall python_agent
python python_agent\training\test_golden_commands.py
.\scripts\dev.ps1 test
.\scripts\dev.ps1 smoke
.\scripts\dev.ps1 build
cd desktop_ui
npm run build
```

