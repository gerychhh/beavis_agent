# Tauri command contract for new UI

The React UI should call one Tauri command:

```ts
invoke("beavis_call", {
  request: {
    id: crypto.randomUUID(),
    method: "commands.run",
    params: {
      text: "открой телеграм",
      execute: true
    }
  }
})
```

The command must return the exact JSON response from Python bridge:

```json
{
  "id": "same request id",
  "ok": true,
  "data": {},
  "error": null,
  "code": null,
  "meta": {}
}
```

## Python bridge

Persistent mode:

```powershell
python -m python_agent.bridge.stdio_server
```

It accepts JSON-lines on stdin and returns JSON-lines on stdout.

One-shot test mode:

```powershell
python -m python_agent.bridge.oneshot system.health
python -m python_agent.bridge.oneshot commands.run "{\"text\":\"звук на 50\",\"execute\":false}"
```

## Methods

- `system.health`
- `commands.run`
- `commands.build_tool_call`
- `commands.reload`
- `apps.list_windows_apps`
- `apps.list_user_apps`
- `apps.add`
- `apps.update_speech_forms`
- `apps.delete`
- `apps.apply_changes`
- `voice.preload`
- `voice.listen_once`
- `voice.test_microphone`
- `settings.load`
- `settings.save`
- `history.list`
- `history.mark`
