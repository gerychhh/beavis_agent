mod bridge;

use serde::{Deserialize, Serialize};
use std::{
    sync::Mutex,
    thread,
    time::{Duration, SystemTime, UNIX_EPOCH},
};
use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Emitter, Manager, WebviewUrl, WebviewWindowBuilder,
};
use tauri_plugin_global_shortcut::{
    Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState,
};

const MAIN_WINDOW_LABEL: &str = "main";
const OVERLAY_WINDOW_LABEL: &str = "beavis_overlay";

#[cfg(windows)]
use windows::Win32::{
    Foundation::HWND,
    System::Threading::{AttachThreadInput, GetCurrentThreadId},
    UI::{
        WindowsAndMessaging::{
            AllowSetForegroundWindow, BringWindowToTop, GetForegroundWindow, GetWindowLongW,
            GetWindowTextLengthW, GetWindowThreadProcessId, IsWindow, IsWindowVisible,
            SetForegroundWindow, SetWindowPos, ShowWindow, SwitchToThisWindow, GWL_EXSTYLE,
            HWND_TOPMOST, SWP_NOMOVE, SWP_NOSIZE, SWP_SHOWWINDOW, SW_RESTORE, SW_SHOW,
            WS_EX_TOOLWINDOW,
        },
    },
};

fn show_main_window(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window(MAIN_WINDOW_LABEL) {
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
    }
}

#[derive(Clone, Copy)]
struct WorkAreaBounds {
    x: f64,
    y: f64,
    width: f64,
    height: f64,
}

#[derive(Clone, Copy)]
struct OverlayGeometry {
    x: f64,
    y: f64,
    width: f64,
    height: f64,
}

fn activation_id() -> String {
    let millis = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis())
        .unwrap_or(0);
    format!("hotkey_{millis}")
}

fn overlay_mode_for_hotkey(kind: &str) -> &'static str {
    if kind == "voice" {
        "voice"
    } else {
        "command"
    }
}

fn overlay_url(mode: &str, activation_id: &str, target_hwnd: Option<&str>) -> String {
    let mut url = format!("index.html?overlay={mode}&activation={activation_id}");
    if let Some(hwnd) = target_hwnd {
        url.push_str("&target_hwnd=");
        url.push_str(hwnd);
    }
    url
}

fn work_area_bounds(app: &tauri::AppHandle) -> WorkAreaBounds {
    let monitor = app
        .get_webview_window(MAIN_WINDOW_LABEL)
        .and_then(|window| window.current_monitor().ok().flatten())
        .or_else(|| app.primary_monitor().ok().flatten())
        .or_else(|| {
            app.available_monitors()
                .ok()
                .and_then(|monitors| monitors.into_iter().next())
        });

    if let Some(monitor) = monitor {
        let work_area = monitor.work_area();
        let scale = monitor.scale_factor();
        return WorkAreaBounds {
            x: f64::from(work_area.position.x) / scale,
            y: f64::from(work_area.position.y) / scale,
            width: f64::from(work_area.size.width) / scale,
            height: f64::from(work_area.size.height) / scale,
        };
    }

    WorkAreaBounds {
        x: 0.0,
        y: 0.0,
        width: 1280.0,
        height: 720.0,
    }
}

fn overlay_geometry(mode: &str, bounds: WorkAreaBounds) -> OverlayGeometry {
    let preferred_width: f64 = if mode == "command" { 760.0 } else { 320.0 };
    let preferred_height: f64 = if mode == "command" { 72.0 } else { 234.0 };
    let width = preferred_width.min(bounds.width - 24.0).max(240.0);
    let height = preferred_height.min(bounds.height - 24.0).max(72.0);
    let preferred_y = bounds.y + 48.0_f64.max(bounds.height * 0.22);
    let max_y = bounds.y + (bounds.height - height - 24.0).max(12.0);

    OverlayGeometry {
        x: bounds.x + ((bounds.width - width) / 2.0).round(),
        y: preferred_y.min(max_y).round(),
        width,
        height,
    }
}

fn create_overlay_window(
    app: &tauri::AppHandle,
    mode: &str,
    target_hwnd: Option<&str>,
) -> Result<(), String> {
    if let Some(existing) = app.get_webview_window(OVERLAY_WINDOW_LABEL) {
        let _ = existing.destroy().or_else(|_| existing.close());
        thread::sleep(Duration::from_millis(120));
    }

    let activation_id = activation_id();
    let geometry = overlay_geometry(mode, work_area_bounds(app));
    let title = if mode == "command" {
        "Beavis Command"
    } else {
        "Beavis Voice"
    };

    let overlay = WebviewWindowBuilder::new(
        app,
        OVERLAY_WINDOW_LABEL,
        WebviewUrl::App(overlay_url(mode, &activation_id, target_hwnd).into()),
    )
    .title(title)
    .position(geometry.x, geometry.y)
    .inner_size(geometry.width, geometry.height)
    .decorations(false)
    .resizable(false)
    .skip_taskbar(true)
    .always_on_top(true)
    .visible_on_all_workspaces(true)
    .focused(true)
    .focusable(true)
    .visible(true)
    .transparent(true)
    .shadow(false)
    .build()
    .map_err(|error| error.to_string())?;

    let _ = overlay.set_always_on_top(true);
    let _ = overlay.set_visible_on_all_workspaces(true);
    let _ = overlay.set_focusable(true);
    force_focus_webview_window(&overlay)
}

#[cfg(windows)]
fn hwnd_token(hwnd: HWND) -> String {
    (hwnd.0 as usize).to_string()
}

#[cfg(windows)]
fn is_user_window(hwnd: HWND) -> bool {
    if hwnd.is_invalid() {
        return false;
    }

    unsafe {
        if !IsWindow(Some(hwnd)).as_bool() || !IsWindowVisible(hwnd).as_bool() {
            return false;
        }

        let ex_style = GetWindowLongW(hwnd, GWL_EXSTYLE) as u32;
        if (ex_style & WS_EX_TOOLWINDOW.0) != 0 {
            return false;
        }

        if GetWindowTextLengthW(hwnd) <= 0 {
            return false;
        }

        let mut process_id = 0u32;
        GetWindowThreadProcessId(hwnd, Some(&mut process_id));
        process_id != 0 && process_id != std::process::id()
    }
}

#[cfg(windows)]
fn foreground_user_hwnd_token() -> Option<String> {
    let hwnd = unsafe { GetForegroundWindow() };
    is_user_window(hwnd).then(|| hwnd_token(hwnd))
}

#[cfg(not(windows))]
fn foreground_user_hwnd_token() -> Option<String> {
    None
}

#[cfg(windows)]
fn last_active_user_hwnd_token(app: &tauri::AppHandle) -> Option<String> {
    if let Some(hwnd) = foreground_user_hwnd_token() {
        if let Ok(mut state) = app.state::<Mutex<ActiveWindowState>>().lock() {
            state.last_user_hwnd = Some(hwnd.clone());
        }
        return Some(hwnd);
    }

    app.state::<Mutex<ActiveWindowState>>()
        .lock()
        .ok()
        .and_then(|state| state.last_user_hwnd.clone())
}

#[cfg(not(windows))]
fn last_active_user_hwnd_token(_app: &tauri::AppHandle) -> Option<String> {
    None
}

#[cfg(windows)]
fn spawn_active_window_tracker(app: tauri::AppHandle) {
    thread::spawn(move || loop {
        if let Some(hwnd) = foreground_user_hwnd_token() {
            if let Ok(mut state) = app.state::<Mutex<ActiveWindowState>>().lock() {
                state.last_user_hwnd = Some(hwnd);
            }
        }
        thread::sleep(Duration::from_millis(150));
    });
}

#[cfg(not(windows))]
fn spawn_active_window_tracker(_app: tauri::AppHandle) {}

fn open_overlay_from_hotkey(app: tauri::AppHandle, kind: String, shortcut: String) {
    let target_hwnd = last_active_user_hwnd_token(&app);
    thread::spawn(move || {
        let mode = overlay_mode_for_hotkey(&kind);
        if create_overlay_window(&app, mode, target_hwnd.as_deref()).is_err() {
            let _ = app.emit_to(
                MAIN_WINDOW_LABEL,
                "beavis-hotkey",
                BeavisHotkeyEvent {
                    kind,
                    shortcut,
                    target_hwnd,
                },
            );
        }
    });
}

#[cfg(windows)]
fn force_focus_webview_window(window: &tauri::WebviewWindow) -> Result<(), String> {
    let hwnd = window.hwnd().map_err(|error| error.to_string())?;
    unsafe {
        let foreground = GetForegroundWindow();
        let current_thread = GetCurrentThreadId();
        let foreground_thread = if !foreground.is_invalid() {
            GetWindowThreadProcessId(foreground, None)
        } else {
            0
        };

        if foreground_thread != 0 && foreground_thread != current_thread {
            let _ = AttachThreadInput(current_thread, foreground_thread, true);
        }

        let _ = AllowSetForegroundWindow(u32::MAX);
        let _ = window.set_focus();
        let _ = window.set_always_on_top(true);
        let _ = window.show();
        let _ = window.unminimize();
        let _ = ShowWindow(hwnd, SW_RESTORE);
        let _ = ShowWindow(hwnd, SW_SHOW);
        let _ = SetWindowPos(
            hwnd,
            Some(HWND_TOPMOST),
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
        );
        let _ = BringWindowToTop(hwnd);
        let _ = SetForegroundWindow(hwnd);
        SwitchToThisWindow(hwnd, true);

        if foreground_thread != 0 && foreground_thread != current_thread {
            let _ = AttachThreadInput(current_thread, foreground_thread, false);
        }
    }
    Ok(())
}

#[cfg(not(windows))]
fn force_focus_webview_window(window: &tauri::WebviewWindow) -> Result<(), String> {
    window.show().map_err(|error| error.to_string())?;
    window.unminimize().map_err(|error| error.to_string())?;
    window.set_focus().map_err(|error| error.to_string())
}

#[tauri::command]
fn force_focus_window(app: tauri::AppHandle, label: String) -> Result<(), String> {
    let window = app
        .get_webview_window(&label)
        .ok_or_else(|| format!("Window not found: {label}"))?;
    force_focus_webview_window(&window)
}

#[derive(Default)]
struct HotkeyState {
    registered: Vec<Shortcut>,
}

#[derive(Default)]
struct ActiveWindowState {
    last_user_hwnd: Option<String>,
}

#[derive(Debug, Deserialize)]
struct GlobalHotkeySettings {
    text_hotkey_enabled: bool,
    text_hotkey_sequence: String,
    voice_hotkey_enabled: bool,
    voice_hotkey_sequence: String,
}

#[derive(Clone, Serialize)]
struct BeavisHotkeyEvent {
    kind: String,
    shortcut: String,
    target_hwnd: Option<String>,
}

#[derive(Serialize)]
struct HotkeyRegistration {
    kind: String,
    shortcut: String,
    ok: bool,
    error: Option<String>,
}

#[tauri::command]
fn configure_global_hotkeys(
    app: tauri::AppHandle,
    state: tauri::State<'_, Mutex<HotkeyState>>,
    settings: GlobalHotkeySettings,
) -> Result<Vec<HotkeyRegistration>, String> {
    let global_shortcut = app.global_shortcut();
    let mut hotkeys = state.lock().map_err(|error| error.to_string())?;

    for shortcut in hotkeys.registered.drain(..) {
        let _ = global_shortcut.unregister(shortcut);
    }

    let mut report = Vec::new();
    if settings.text_hotkey_enabled {
        register_first_available_hotkey(
            &app,
            "text",
            &settings.text_hotkey_sequence,
            &mut hotkeys.registered,
            &mut report,
        );
    }
    if settings.voice_hotkey_enabled {
        register_first_available_hotkey(
            &app,
            "voice",
            &settings.voice_hotkey_sequence,
            &mut hotkeys.registered,
            &mut report,
        );
    }

    Ok(report)
}

fn register_first_available_hotkey(
    app: &tauri::AppHandle,
    kind: &str,
    sequence: &str,
    registered: &mut Vec<Shortcut>,
    report: &mut Vec<HotkeyRegistration>,
) {
    let variants = hotkey_variants(sequence);
    if variants.is_empty() {
        report.push(HotkeyRegistration {
            kind: kind.to_string(),
            shortcut: sequence.to_string(),
            ok: false,
            error: Some("empty shortcut".to_string()),
        });
        return;
    }

    let mut last_error = None;
    for (label, shortcut) in variants {
        let emit_kind = kind.to_string();
        let emit_shortcut = label.clone();
        let app_for_handler = app.clone();
        match app.global_shortcut().on_shortcut(shortcut, move |_app, _shortcut, event| {
            if event.state == ShortcutState::Pressed {
                open_overlay_from_hotkey(
                    app_for_handler.clone(),
                    emit_kind.clone(),
                    emit_shortcut.clone(),
                );
            }
        }) {
            Ok(()) => {
                registered.push(shortcut);
                report.push(HotkeyRegistration {
                    kind: kind.to_string(),
                    shortcut: label,
                    ok: true,
                    error: None,
                });
                return;
            }
            Err(error) => {
                last_error = Some(error.to_string());
            }
        }
    }

    report.push(HotkeyRegistration {
        kind: kind.to_string(),
        shortcut: sequence.to_string(),
        ok: false,
        error: last_error,
    });
}

fn hotkey_variants(sequence: &str) -> Vec<(String, Shortcut)> {
    let parts: Vec<String> = sequence
        .split('+')
        .map(|part| part.trim())
        .filter(|part| !part.is_empty())
        .map(|part| part.to_string())
        .collect();
    if parts.is_empty() {
        return Vec::new();
    }

    let mut modifier_variants: Vec<(String, Modifiers)> = vec![("".to_string(), Modifiers::empty())];
    let mut code: Option<(String, Code)> = None;

    for part in parts {
        let lower = part.to_lowercase();
        match lower.as_str() {
            "ctrl" | "control" | "cmdorcontrol" | "commandorcontrol" => {
                #[cfg(windows)]
                add_modifier_variants(&mut modifier_variants, &[("Ctrl", Modifiers::CONTROL)]);
                #[cfg(not(windows))]
                add_modifier_variants(
                    &mut modifier_variants,
                    &[("Ctrl", Modifiers::CONTROL), ("CmdOrCtrl", Modifiers::SUPER)],
                );
            }
            "cmd" | "command" | "meta" | "super" | "win" => {
                add_modifier_variants(&mut modifier_variants, &[("Super", Modifiers::SUPER)]);
            }
            "alt" | "option" => {
                add_modifier_variants(&mut modifier_variants, &[("Alt", Modifiers::ALT)]);
            }
            "shift" => {
                add_modifier_variants(&mut modifier_variants, &[("Shift", Modifiers::SHIFT)]);
            }
            _ => {
                code = parse_hotkey_code(&part);
            }
        }
    }

    let Some((code_label, code_value)) = code else {
        return Vec::new();
    };

    let mut variants = Vec::new();
    for (modifier_label, modifiers) in modifier_variants {
        let label = if modifier_label.is_empty() {
            code_label.clone()
        } else {
            format!("{modifier_label}+{code_label}")
        };
        variants.push((label, Shortcut::new(Some(modifiers), code_value)));
    }
    variants
}

fn add_modifier_variants(
    variants: &mut Vec<(String, Modifiers)>,
    additions: &[(&str, Modifiers)],
) {
    let current = std::mem::take(variants);
    for (label, modifiers) in current {
        for (addition_label, addition_modifier) in additions {
            let next_label = if label.is_empty() {
                (*addition_label).to_string()
            } else {
                format!("{label}+{addition_label}")
            };
            variants.push((next_label, modifiers | *addition_modifier));
        }
    }
}

fn parse_hotkey_code(part: &str) -> Option<(String, Code)> {
    let lower = part.to_lowercase();
    let code = match lower.as_str() {
        "space" | " " => Code::Space,
        "escape" | "esc" => Code::Escape,
        "enter" | "return" => Code::Enter,
        "tab" => Code::Tab,
        "backspace" => Code::Backspace,
        "delete" | "del" => Code::Delete,
        "insert" | "ins" => Code::Insert,
        "home" => Code::Home,
        "end" => Code::End,
        "pageup" | "page_up" => Code::PageUp,
        "pagedown" | "page_down" => Code::PageDown,
        "arrowup" | "up" => Code::ArrowUp,
        "arrowdown" | "down" => Code::ArrowDown,
        "arrowleft" | "left" => Code::ArrowLeft,
        "arrowright" | "right" => Code::ArrowRight,
        "f1" => Code::F1,
        "f2" => Code::F2,
        "f3" => Code::F3,
        "f4" => Code::F4,
        "f5" => Code::F5,
        "f6" => Code::F6,
        "f7" => Code::F7,
        "f8" => Code::F8,
        "f9" => Code::F9,
        "f10" => Code::F10,
        "f11" => Code::F11,
        "f12" => Code::F12,
        _ => {
            let mut chars = part.chars();
            let first = chars.next()?;
            if chars.next().is_some() {
                return None;
            }
            match first.to_ascii_uppercase() {
                'A' => Code::KeyA,
                'B' => Code::KeyB,
                'C' => Code::KeyC,
                'D' => Code::KeyD,
                'E' => Code::KeyE,
                'F' => Code::KeyF,
                'G' => Code::KeyG,
                'H' => Code::KeyH,
                'I' => Code::KeyI,
                'J' => Code::KeyJ,
                'K' => Code::KeyK,
                'L' => Code::KeyL,
                'M' => Code::KeyM,
                'N' => Code::KeyN,
                'O' => Code::KeyO,
                'P' => Code::KeyP,
                'Q' => Code::KeyQ,
                'R' => Code::KeyR,
                'S' => Code::KeyS,
                'T' => Code::KeyT,
                'U' => Code::KeyU,
                'V' => Code::KeyV,
                'W' => Code::KeyW,
                'X' => Code::KeyX,
                'Y' => Code::KeyY,
                'Z' => Code::KeyZ,
                '0' => Code::Digit0,
                '1' => Code::Digit1,
                '2' => Code::Digit2,
                '3' => Code::Digit3,
                '4' => Code::Digit4,
                '5' => Code::Digit5,
                '6' => Code::Digit6,
                '7' => Code::Digit7,
                '8' => Code::Digit8,
                '9' => Code::Digit9,
                _ => return None,
            }
        }
    };

    Some((part.to_string(), code))
}

fn build_tray(app: &mut tauri::App) -> tauri::Result<()> {
    let show = MenuItem::with_id(app, "show", "Show Beavis", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&show, &quit])?;
    let icon = app.default_window_icon().cloned();

    let mut builder = TrayIconBuilder::new()
        .menu(&menu)
        .show_menu_on_left_click(false)
        .tooltip("Beavis Agent")
        .on_menu_event(|app, event| match event.id().as_ref() {
            "show" => show_main_window(app),
            "quit" => app.exit(0),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| match event {
            TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            }
            | TrayIconEvent::DoubleClick {
                button: MouseButton::Left,
                ..
            } => show_main_window(tray.app_handle()),
            _ => {}
        });

    if let Some(icon) = icon {
        builder = builder.icon(icon);
    }

    let tray = builder.build(app)?;
    app.manage(tray);
    Ok(())
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .manage(bridge::BridgeState::default())
        .manage(Mutex::new(HotkeyState::default()))
        .manage(Mutex::new(ActiveWindowState::default()))
        .invoke_handler(tauri::generate_handler![
            bridge::beavis_call,
            force_focus_window,
            configure_global_hotkeys
        ])
        .setup(|app| {
            build_tray(app)?;
            spawn_active_window_tracker(app.handle().clone());
            Ok(())
        })
        .on_window_event(|window, event| {
            if window.label() != "main" {
                return;
            }
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running Beavis desktop UI");
}
