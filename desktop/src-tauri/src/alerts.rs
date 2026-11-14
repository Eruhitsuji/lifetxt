use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Mutex;

use tauri::{AppHandle, Manager, State, ipc::CapabilityBuilder};

pub struct DesktopAlerts {
    preference_path: PathBuf,
    enabled: Mutex<bool>,
}

impl DesktopAlerts {
    pub fn new(preference_path: PathBuf) -> Self {
        let enabled = preference_path.is_file();
        Self {
            preference_path,
            enabled: Mutex::new(enabled),
        }
    }

    fn set_enabled(&self, enabled: bool) -> std::io::Result<()> {
        let mut preference = self.enabled.lock().unwrap();
        if *preference == enabled {
            return Ok(());
        }
        update_preference(&self.preference_path, enabled)?;
        *preference = enabled;
        Ok(())
    }
}

fn update_preference(path: &Path, enabled: bool) -> std::io::Result<()> {
    if enabled {
        fs::create_dir_all(path.parent().expect("alert preference has a directory"))?;
        fs::OpenOptions::new()
            .create(true)
            .write(true)
            .truncate(false)
            .open(path)?;
    } else if let Err(error) = fs::remove_file(path) {
        if error.kind() != std::io::ErrorKind::NotFound {
            return Err(error);
        }
    }
    Ok(())
}

pub fn grant_webview_access(app: &AppHandle, origin: &str) -> tauri::Result<()> {
    app.add_capability(
        CapabilityBuilder::new("lifetxt-desktop-alerts")
            .local(false)
            .remote(format!("{origin}/*"))
            .webview("main")
            .permission("allow-desktop-alerts-enabled")
            .permission("allow-set-desktop-alerts-enabled")
            .permission("allow-send-desktop-alert"),
    )
}

#[tauri::command]
pub fn desktop_alerts_enabled(alerts: State<'_, DesktopAlerts>) -> bool {
    *alerts.enabled.lock().unwrap()
}

#[tauri::command]
pub fn set_desktop_alerts_enabled(
    alerts: State<'_, DesktopAlerts>,
    enabled: bool,
) -> Result<(), String> {
    alerts
        .set_enabled(enabled)
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub async fn send_desktop_alert(
    app: AppHandle,
    test: bool,
    manual: bool,
    japanese: bool,
) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        // Hold the preference lock until the OS request finishes so disabling
        // alerts also stops queued automatic deliveries.
        let alerts = app.state::<DesktopAlerts>();
        let enabled = alerts.enabled.lock().unwrap();
        if !test && !manual && !*enabled {
            return Err("Automatic alerts are disabled".into());
        }
        let body = match (test, japanese) {
            (true, true) => "テスト通知です。",
            (true, false) => "This is a test notification.",
            (false, true) => "通知の詳細は life.txt で確認できます。",
            (false, false) => "Open life.txt to view the notification.",
        };
        let mut notification = notify_rust::Notification::new();
        notification.summary("lifetxt Desktop").body(body);
        #[cfg(target_os = "windows")]
        notification.app_id(&app.config().identifier);
        #[cfg(target_os = "macos")]
        notify_rust::set_application(&app.config().identifier)
            .map_err(|error| error.to_string())?;
        notification
            .show()
            .map(|_| ())
            .map_err(|error| error.to_string())
    })
    .await
    .map_err(|error| error.to_string())?
}
