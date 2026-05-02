# window_control

`window_control` controls existing visible Windows windows.

Pipeline:

```text
text
-> skill_classifier: window_control
-> window_control_arg_model
-> ToolCall JSON
-> C++ WindowControlSkill
```

Argument model output:

```json
{
  "action": "minimize",
  "target_type": "current",
  "confidence": 0.91
}
```

```json
{
  "action": "close",
  "target_type": "app",
  "app_id": "notepad",
  "confidence": 0.88
}
```

Supported actions:

- `close`
- `minimize`
- `maximize`
- `restore`

Targets:

- `current` means the foreground window.
- `app` means a visible window matched by canonical `app_id`.

Training commands:

```powershell
python python_agent/training/generate_window_control_dataset.py
python python_agent/training/train_window_control_arg_model.py
python python_agent/training/test_window_control_arg_model.py
```

The C++ skill uses normal Windows messages:

- `ShowWindow(..., SW_MINIMIZE)`
- `ShowWindow(..., SW_MAXIMIZE)`
- `ShowWindow(..., SW_RESTORE)`
- `PostMessageW(..., WM_CLOSE)`

For `maximize` and `restore`, the skill also activates the window and brings it
to the foreground. A maximized window hidden behind another app should become
the top active window.
