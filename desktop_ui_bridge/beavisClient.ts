// Minimal TypeScript client for the new UI.
// It expects a Tauri command named `beavis_call`.
// The UI generator can use this file as the only Beavis integration point.

import { invoke } from "@tauri-apps/api/core";

export type BeavisApiResponse<T = unknown> = {
  id?: string | number | null;
  ok: boolean;
  data: T | null;
  error: string | null;
  code: string | null;
  meta: Record<string, unknown>;
};

export type BeavisMethod =
  | "system.health"
  | "commands.run"
  | "commands.build_tool_call"
  | "commands.reload"
  | "apps.list_windows_apps"
  | "apps.list_user_apps"
  | "apps.add"
  | "apps.update_speech_forms"
  | "apps.delete"
  | "apps.apply_changes"
  | "voice.preload"
  | "voice.listen_once"
  | "voice.test_microphone"
  | "settings.load"
  | "settings.save"
  | "history.list"
  | "history.mark";

export async function beavisCall<T = unknown>(
  method: BeavisMethod,
  params: Record<string, unknown> = {},
): Promise<BeavisApiResponse<T>> {
  return await invoke<BeavisApiResponse<T>>("beavis_call", {
    request: {
      id: crypto.randomUUID(),
      method,
      params,
    },
  });
}

export async function runCommand(text: string, execute = true) {
  return beavisCall("commands.run", {
    text,
    execute,
    source: "text",
  });
}

export async function buildToolCall(text: string) {
  return beavisCall("commands.build_tool_call", {
    text,
    source: "text",
  });
}

export async function listUserApps() {
  return beavisCall("apps.list_user_apps");
}

export async function listWindowsApps() {
  return beavisCall("apps.list_windows_apps");
}

export async function addApp(payload: {
  display_name: string;
  path?: string;
  app_id?: string;
  speech_forms?: string[];
  windows_app_id?: string;
  launch_type?: string;
  launch_target?: string;
  retrain?: boolean;
}) {
  return beavisCall("apps.add", payload);
}

export async function updateAppSpeechForms(
  app_id: string,
  speech_forms: string[],
  retrain = true,
) {
  return beavisCall("apps.update_speech_forms", {
    app_id,
    speech_forms,
    retrain,
  });
}

export async function deleteApp(app_id: string, retrain = true) {
  return beavisCall("apps.delete", {
    app_id,
    retrain,
  });
}

export async function loadSettings() {
  return beavisCall("settings.load");
}

export async function saveSettings(settings: Record<string, unknown>) {
  return beavisCall("settings.save", {
    settings,
  });
}

export async function listHistory(limit = 120) {
  return beavisCall("history.list", {
    limit,
  });
}
