use serde_json::{json, Value};
use std::{
    env,
    io::{BufRead, BufReader, Write},
    path::PathBuf,
    process::{Child, ChildStdin, ChildStdout, Command, Stdio},
    sync::{Arc, Mutex},
    time::{SystemTime, UNIX_EPOCH},
};

pub struct BridgeState {
    child: Arc<Mutex<Option<BridgeProcess>>>,
}

impl Default for BridgeState {
    fn default() -> Self {
        Self {
            child: Arc::new(Mutex::new(None)),
        }
    }
}

struct BridgeProcess {
    child: Child,
    stdin: ChildStdin,
    stdout: BufReader<ChildStdout>,
}

fn repo_root() -> Result<PathBuf, String> {
    if let Ok(value) = env::var("BEAVIS_REPO_ROOT") {
        let path = PathBuf::from(value);
        if path.exists() {
            return Ok(path);
        }
    }

    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    manifest_dir
        .parent()
        .and_then(|desktop_ui| desktop_ui.parent())
        .map(|path| path.to_path_buf())
        .ok_or_else(|| "Failed to resolve Beavis repo root".to_string())
}

fn python_executable() -> String {
    env::var("BEAVIS_PYTHON").unwrap_or_else(|_| "python".to_string())
}

fn spawn_bridge() -> Result<BridgeProcess, String> {
    let root = repo_root()?;
    let python = python_executable();

    let mut child = Command::new(python)
        .args(["-m", "python_agent.bridge.stdio_server"])
        .current_dir(root)
        .env("PYTHONIOENCODING", "utf-8")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit())
        .spawn()
        .map_err(|error| format!("Failed to start Python bridge: {error}"))?;

    let stdin = child
        .stdin
        .take()
        .ok_or_else(|| "Failed to open bridge stdin".to_string())?;
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| "Failed to open bridge stdout".to_string())?;

    Ok(BridgeProcess {
        child,
        stdin,
        stdout: BufReader::new(stdout),
    })
}

fn request_id() -> String {
    let millis = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis())
        .unwrap_or(0);
    format!("ui_{millis}")
}

#[tauri::command]
pub async fn beavis_call(
    method: String,
    params: Value,
    state: tauri::State<'_, BridgeState>,
) -> Result<Value, String> {
    let child = Arc::clone(&state.child);
    tauri::async_runtime::spawn_blocking(move || beavis_call_blocking(method, params, child))
        .await
        .map_err(|error| format!("Bridge worker failed: {error}"))?
}

fn beavis_call_blocking(
    method: String,
    params: Value,
    child: Arc<Mutex<Option<BridgeProcess>>>,
) -> Result<Value, String> {
    let mut guard = child
        .lock()
        .map_err(|_| "Bridge mutex poisoned".to_string())?;

    let needs_spawn = guard
        .as_mut()
        .map(|process| process.child.try_wait().ok().flatten().is_some())
        .unwrap_or(true);

    if needs_spawn {
        *guard = Some(spawn_bridge()?);
    }

    let process = guard
        .as_mut()
        .ok_or_else(|| "Bridge process is not available".to_string())?;

    let id = request_id();
    let request = json!({
        "id": id,
        "method": method,
        "params": params,
    });

    let line = serde_json::to_string(&request)
        .map_err(|error| format!("Failed to encode bridge request: {error}"))?;

    writeln!(process.stdin, "{line}")
        .and_then(|_| process.stdin.flush())
        .map_err(|error| format!("Failed to write to bridge: {error}"))?;

    let mut response_line = String::new();
    process
        .stdout
        .read_line(&mut response_line)
        .map_err(|error| format!("Failed to read bridge response: {error}"))?;

    if response_line.trim().is_empty() {
        *guard = None;
        return Err("Bridge returned empty response".to_string());
    }

    serde_json::from_str::<Value>(&response_line)
        .map_err(|error| format!("Invalid bridge JSON response: {error}; raw={response_line}"))
}
