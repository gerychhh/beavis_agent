mod bridge;

use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Manager,
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
        .invoke_handler(tauri::generate_handler![
            bridge::beavis_call,
            force_focus_window
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
