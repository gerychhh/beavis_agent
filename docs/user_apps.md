# User Apps

Beavis can learn local user applications without changing runtime code.

The user flow is:

```text
UI -> user app catalog -> apps index -> generated local datasets -> retrained models
```

Local catalog:

```text
python_agent/data/user_apps/apps.json
```

This file is ignored by git because it contains local paths and personal speech
forms.

Example:

```json
{
  "schema_version": 1,
  "apps": [
    {
      "app_id": "my_tool",
      "display_name": "My Tool",
      "launch_type": "exe",
      "launch_target": "D:\\Tools\\MyTool\\mytool.exe",
      "target_path": "D:\\Tools\\MyTool\\mytool.exe",
      "working_directory": "D:\\Tools\\MyTool",
      "speech_forms": ["мой тул", "тулза"]
    }
  ]
}
```

CLI:

```powershell
python -m python_agent.training.add_user_app `
  --path "D:\Tools\MyTool\mytool.exe" `
  --display-name "My Tool" `
  --speech-form "мой тул" `
  --speech-form "тулза"
```

Windows Start/Search and Microsoft Store apps can be added by AppID without
looking for an `.exe` path:

```powershell
python -m python_agent.training.add_user_app `
  --windows-app-id "OpenAI.Codex_2p2nqsd0c76g0!App" `
  --display-name "Codex" `
  --speech-form "кодекс"
```

Those records use `launch_type: "apps_folder"` and launch through
`shell:AppsFolder\<AppID>`. The desktop UI exposes both flows: `Из списка
Windows` and `По пути .exe`.

Update speech forms for an existing app and retrain:

```powershell
python -m python_agent.training.add_user_app `
  --update `
  --app-id "my_tool" `
  --speech-form "мой тул" `
  --speech-form "рабочая прога"
```

Delete an app from the user catalog and retrain:

```powershell
python -m python_agent.training.add_user_app `
  --delete `
  --app-id "my_tool"
```

Storage:

- user app catalog: `python_agent/data/user_apps/apps.json`;
- local generated datasets after retraining: `python_agent/data/user_apps/generated/`;
- app resolver cache: `python_agent/data/cache/apps_index.json`;
- updated model files: `python_agent/models/open_app_arg_model.joblib` and `python_agent/models/skill_classifier.joblib`.

The catalog and generated local data are ignored by git because they can contain
personal paths and speech forms.

The command:

- saves the app to the local catalog;
- rebuilds `python_agent/data/cache/apps_index.json`;
- generates local augmented datasets under `python_agent/data/user_apps/generated/`;
- retrains `open_app_arg_model.joblib` and `skill_classifier.joblib`;
- runs model tests and smoke checks.

The C++ runtime does not need changes. It receives the same `app_id` as before
and resolves it through the updated app index.
