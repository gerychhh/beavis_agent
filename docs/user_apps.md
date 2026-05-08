# User Apps

User apps let Beavis learn local applications without changing runtime code.

Flow:

```text
UI or CLI
-> user app catalog
-> app index
-> generated local datasets
-> retrained local models
```

Local catalog:

```text
python_agent/data/user_apps/apps.json
```

This path is ignored because it may contain personal paths and custom speech
forms.

## Add An EXE App

```powershell
python -m python_agent.training.add_user_app `
  --path "D:\Tools\MyTool\mytool.exe" `
  --display-name "My Tool" `
  --speech-form "мой тул" `
  --speech-form "тулза"
```

## Add A Windows AppID

```powershell
python -m python_agent.training.add_user_app `
  --windows-app-id "OpenAI.Codex_2p2nqsd0c76g0!App" `
  --display-name "Codex" `
  --speech-form "кодекс"
```

Windows AppID records use:

```text
launch_type = apps_folder
launch_target = shell:AppsFolder\<AppID>
```

## Update Speech Forms

```powershell
python -m python_agent.training.add_user_app `
  --update `
  --app-id "my_tool" `
  --speech-form "мой тул" `
  --speech-form "рабочая прога"
```

## Delete A User App

```powershell
python -m python_agent.training.add_user_app `
  --delete `
  --app-id "my_tool"
```

## Generated Files

```text
python_agent/data/user_apps/apps.json
python_agent/data/user_apps/generated/
python_agent/data/cache/apps_index.json
python_agent/models/open_app_arg_model.joblib
python_agent/models/skill_classifier.joblib
```

The C++ runtime does not need changes. It receives the same stable `app_id` and
resolves it through the refreshed app index.
