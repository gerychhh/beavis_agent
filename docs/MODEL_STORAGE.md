# Model Storage

Generated model files are local artifacts. Do not commit them.

Ignored model paths:

```text
python_agent/models/*
python_agent/models/stt/*
```

Tracked placeholders:

```text
python_agent/models/.gitkeep
python_agent/models/stt/.gitkeep
```

## Why

```text
Model files can be large.
Downloaded STT models are very large.
Joblib files can depend on exact sklearn/joblib versions.
Models can be regenerated from training scripts.
Local models may differ between machines.
```

## Expected Workflow

```powershell
python -m pip install -r requirements.txt
.\scripts\dev.ps1 train
.\scripts\dev.ps1 test
```

Use the same Python environment for training, testing, and running the app.

## Check Tracked Models

```powershell
git ls-files python_agent/models/
```

Good output:

```text
python_agent/models/.gitkeep
python_agent/models/stt/.gitkeep
```

Bad output:

```text
python_agent/models/skill_classifier.joblib
python_agent/models/open_app_arg_model.joblib
python_agent/models/volume_set_arg_model.joblib
python_agent/models/window_control_arg_model.joblib
python_agent/models/window_layout_arg_model.joblib
```

If generated models were tracked accidentally:

```powershell
git rm -r --cached python_agent/models/
git add python_agent/models/.gitkeep
git add python_agent/models/stt/.gitkeep
```

Do not delete local model files unless you want to retrain or redownload them.
