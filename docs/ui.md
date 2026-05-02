# Beavis Agent UI

Desktop UI lives in `python_agent/ui`.

Run:

```powershell
python -m python_agent.ui.app
```

Useful modes:

```powershell
python -m python_agent.ui.app --hidden
python -m python_agent.ui.app --no-hotkey
```

What is included:

- command input with optional execution;
- system tray icon;
- overlay command line above other windows;
- configurable global hotkey;
- adding local applications with retraining;
- command history from `python_agent/data/logs/actions.jsonl`;
- recognition feedback saved to `python_agent/data/feedback/command_feedback.jsonl`.

The history tab can mark a command as `correct` or `incorrect`. Those marks are
kept separately from the action log, so retraining scripts can later consume
confirmed examples without mutating the original runtime log.
