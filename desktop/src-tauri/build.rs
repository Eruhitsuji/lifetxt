fn main() {
    tauri_build::try_build(tauri_build::Attributes::new().app_manifest(
        tauri_build::AppManifest::new().commands(&[
            "desktop_alerts_enabled",
            "set_desktop_alerts_enabled",
            "send_desktop_alert",
        ]),
    ))
    .expect("could not build desktop app manifest");
}
