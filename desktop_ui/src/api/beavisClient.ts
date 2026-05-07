import { invoke } from "@tauri-apps/api/core";

export type ApiResult<T = unknown> = {
  ok: boolean;
  data: T | null;
  error: string | null;
  code: string | null;
  meta: Record<string, unknown>;
};

const DEBUG =
  import.meta.env.DEV || localStorage.getItem("beavis.debug") === "1";

function makeRequestId() {
  return `ui_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

export async function beavisCall<T = unknown>(
  method: string,
  params: Record<string, unknown> = {},
): Promise<ApiResult<T>> {
  const requestId = makeRequestId();
  const started = performance.now();

  if (DEBUG) {
    console.groupCollapsed(
      `%c[beavis api] → ${method}`,
      "color:#9ca3af;font-weight:bold",
    );
    console.log("request_id:", requestId);
    console.log("params:", params);
  }

  try {
    const result = await invoke<ApiResult<T>>("beavis_call", {
      method,
      params,
    });

    if (DEBUG) {
      console.log("response:", result);
      console.log("time_ms:", Math.round(performance.now() - started));
      console.groupEnd();
    }

    window.dispatchEvent(
      new CustomEvent("beavis-api-log", {
        detail: {
          requestId,
          method,
          params,
          result,
          timeMs: Math.round(performance.now() - started),
        },
      }),
    );

    return result;
  } catch (error) {
    const result: ApiResult<T> = {
      ok: false,
      data: null,
      error: String(error),
      code: "TAURI_INVOKE_ERROR",
      meta: { requestId },
    };

    if (DEBUG) {
      console.error("invoke error:", error);
      console.groupEnd();
    }

    window.dispatchEvent(
      new CustomEvent("beavis-api-log", {
        detail: {
          requestId,
          method,
          params,
          result,
          timeMs: Math.round(performance.now() - started),
        },
      }),
    );

    return result;
  }
}
