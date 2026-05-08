# Documentation Index

This folder is the technical map for Beavis Agent. Keep it aligned with the
actual code; outdated docs are treated as project debt.

## Start Here

```text
README.md                 Project overview, quick start, common commands
docs/SETUP_AND_RUN.md     Full setup, build, run, test, and troubleshooting
docs/ARCHITECTURE.md      Layer ownership and command flow
docs/COMMAND_PROTOCOL.md  JSON protocol between Python and C++
docs/SKILL_DEVELOPMENT.md How to add or change a skill
```

## Supporting Docs

```text
docs/MODEL_STORAGE.md     Which model files are local and ignored
docs/PROJECT_CONTEXT.md   Product constraints and refactor intent
docs/REFACTOR_PLAN.md     Current simplification plan
docs/app_index.md         App discovery and app_id resolution
docs/user_apps.md         User-managed local app catalog
docs/skill_classifier.md  Top-level skill classifier behavior
docs/window_control.md    window_control implementation notes
docs/ui.md                Desktop UI bridge and build notes
```

## Documentation Rules

```text
Prefer the current code over older plans.
Document user-facing protocols in COMMAND_PROTOCOL.md.
Document new skills in SKILL_DEVELOPMENT.md and COMMAND_PROTOCOL.md.
Document local setup changes in SETUP_AND_RUN.md.
Do not document generated files as committed source files.
```

