mod bridge;

use serde::{Deserialize, Serialize};
use std::sync::Mutex;
use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Emitter, Manager,
};
use tauri_plugin_global_shortcut::{
    Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState,
};

#[cfg(windows)]
use windows::Win32::{
    System::Threading::{AttachThreadInput, GetCurrentThreadId},
    UI::{
        WindowsAndMessaging::{
            AllowSetForegroundWindow, BringWindowToTop, GetForegroundWindow,
            GetWindowThreadProcessId, SetForegroundWindow, SetWindowPos, ShowWindow,
            SwitchToThisWindow, HWND_TOPMOST, SWP_NOMOVE, SWP_NOSIZE, SWP_SHOWWINDOW,
            SW_RESTORE, SW_SHOW,
        },
    },
};

fn show_main_window(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
    }
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
                show_main_window(&app_for_handler);
                let _ = app_for_handler.emit_to(
                    "main",
                    "beavis-hotkey",
                    BeavisHotkeyEvent {
                        kind: emit_kind.clone(),
                        shortcut: emit_shortcut.clone(),
                    },
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
        .invoke_handler(tauri::generate_handler![
            bridge::beavis_call,
            force_focus_window,
            configure_global_hotkeys
        ])
        .setup(|app| {
            build_tray(app)?;
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
