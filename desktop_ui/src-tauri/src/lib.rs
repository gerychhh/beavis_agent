mod bridge;

pub fn run() {
    tauri::Builder::default()
        .manage(bridge::BridgeState::default())
        .invoke_handler(tauri::generate_handler![bridge::beavis_call])
        .run(tauri::generate_context!())
        .expect("error while running Beavis desktop UI");
}
