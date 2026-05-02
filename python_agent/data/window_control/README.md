# window_control dataset

Argument model data for the `window_control` skill.

Files:

- `processed/action_train.csv` maps normalized command text to `close|minimize|maximize|restore|unknown`.
- `processed/target_train.csv` maps the same text to `current`, an `app_id`, or `unknown`.
- `processed/combined_examples.jsonl` stores expected extractor outputs.
- `eval/manual_tests.jsonl` stores stable regression examples.
- `feedback/corrections.jsonl` is reserved for confirmed fixes from logs.

Regenerate and retrain:

```powershell
python python_agent/training/generate_window_control_dataset.py
python python_agent/training/train_window_control_arg_model.py
python python_agent/training/test_window_control_arg_model.py
```
