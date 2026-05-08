# window_control

`window_control` controls existing visible Windows windows.

Pipeline:

```text
text
-> skill_classifier: window_control
-> window_control extractor
-> ToolCall JSON
-> C++ WindowControlSkill
```

Example current-window args:

```json
{
  "action": "close",
  "target_type": "current"
}
```

Example app-window args:

```json
{
  "action": "minimize",
  "target_type": "app",
  "app_id": "telegram"
}
```

Supported actions:

```text
close
minimize
maximize
restore
```

Targets:

```text
current   foreground window
app       visible window matched by app_id
```

Training:

```powershell
python python_agent/training/generate_window_control_dataset.py
python python_agent/training/train_window_control_arg_model.py
python python_agent/training/test_window_control_arg_model.py
```

C++ uses normal Windows operations:

```text
ShowWindow(..., SW_MINIMIZE)
ShowWindow(..., SW_MAXIMIZE)
ShowWindow(..., SW_RESTORE)
PostMessageW(..., WM_CLOSE)
```
