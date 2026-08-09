// Companion-process desktop shell for lifetxt (issue #233, first slice).
//
// This binary owns no life.txt logic of its own. It locates an already
// installed `lifetxt`, spawns `lifetxt serve` as a child process on a
// freshly reserved local port, waits for it to answer /api/health, then
// points the window at it. Closing the window or exiting the app kills
// the spawned server so no orphaned process or bound port survives.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::TcpListener;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::{Manager, RunEvent, WindowEvent};

struct ServerProcess(Mutex<Option<Child>>);

/// Candidates tried, in order, to locate an installed lifetxt. The first
/// whose `--version` invocation exits successfully wins (Requirement 1.1).
fn backend_candidates() -> Vec<Vec<&'static str>> {
    vec![
        vec!["lifetxt"],
        vec!["python", "-m", "lifetxt"],
        vec!["python3", "-m", "lifetxt"],
        vec!["py", "-m", "lifetxt"],
    ]
}

fn command_with_no_window(program: &str) -> Command {
    let mut command = Command::new(program);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        command.creation_flags(CREATE_NO_WINDOW);
    }
    command
}

fn find_backend() -> Option<Vec<String>> {
    for candidate in backend_candidates() {
        let (program, args) = candidate.split_first().expect("candidate is non-empty");
        let mut cmd = command_with_no_window(program);
        cmd.args(args)
            .arg("--version")
            .stdout(Stdio::null())
            .stderr(Stdio::null());
        if let Ok(status) = cmd.status() {
            if status.success() {
                return Some(candidate.iter().map(|s| s.to_string()).collect());
            }
        }
    }
    None
}

fn reserve_port() -> std::io::Result<u16> {
    let listener = TcpListener::bind("127.0.0.1:0")?;
    let port = listener.local_addr()?.port();
    drop(listener);
    Ok(port)
}

fn spawn_server(backend: &[String], port: u16) -> std::io::Result<Child> {
    let (program, prefix_args) = backend.split_first().expect("backend is non-empty");
    let mut cmd = command_with_no_window(program);
    cmd.args(prefix_args)
        .args(["serve", "--host", "127.0.0.1", "--port"])
        .arg(port.to_string())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    cmd.spawn()
}

fn wait_for_health(port: u16, timeout: Duration) -> bool {
    let url = format!("http://127.0.0.1:{port}/api/health");
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if let Ok(response) = ureq::get(&url).call() {
            if response.status().is_success() {
                return true;
            }
        }
        std::thread::sleep(Duration::from_millis(200));
    }
    false
}

fn escape_js_string(text: &str) -> String {
    text.replace('\\', "\\\\")
        .replace('\'', "\\'")
        .replace('\n', "\\n")
}

fn show_error(window: &tauri::WebviewWindow, message: &str) {
    let script = format!(
        "document.body.innerHTML = '<pre style=\"font-family:sans-serif;padding:2rem;white-space:pre-wrap;\">{}</pre>';",
        escape_js_string(message)
    );
    let _ = window.eval(&script);
}

fn take_child(app_handle: &tauri::AppHandle) -> Option<Child> {
    app_handle
        .try_state::<ServerProcess>()
        .and_then(|state| state.0.lock().unwrap().take())
}

fn kill_server(app_handle: &tauri::AppHandle) {
    if let Some(mut child) = take_child(app_handle) {
        let _ = child.kill();
        let _ = child.wait();
    }
}

fn main() {
    tauri::Builder::default()
        .manage(ServerProcess(Mutex::new(None)))
        .setup(|app| {
            let app_handle = app.handle().clone();
            std::thread::spawn(move || {
                let Some(window) = app_handle.get_webview_window("main") else {
                    return;
                };

                let Some(backend) = find_backend() else {
                    show_error(
                        &window,
                        "Could not find an installed lifetxt.\n\n\
                         Tried: lifetxt, python -m lifetxt, python3 -m lifetxt, py -m lifetxt.\n\n\
                         Install lifetxt (pip install -e .) and confirm `lifetxt --version` \
                         works from a terminal, then restart this app.",
                    );
                    return;
                };

                let port = match reserve_port() {
                    Ok(port) => port,
                    Err(err) => {
                        show_error(&window, &format!("Could not reserve a local port: {err}"));
                        return;
                    }
                };

                let child = match spawn_server(&backend, port) {
                    Ok(child) => child,
                    Err(err) => {
                        show_error(&window, &format!("Could not start lifetxt serve: {err}"));
                        return;
                    }
                };

                if let Some(state) = app_handle.try_state::<ServerProcess>() {
                    *state.0.lock().unwrap() = Some(child);
                }

                if wait_for_health(port, Duration::from_secs(15)) {
                    let url = format!("http://127.0.0.1:{port}/");
                    let script =
                        format!("window.location.replace('{}');", escape_js_string(&url));
                    let _ = window.eval(&script);
                } else {
                    show_error(
                        &window,
                        "lifetxt serve did not become ready within 15 seconds.\n\n\
                         Try running `lifetxt serve` from a terminal to see the actual error.",
                    );
                    kill_server(&app_handle);
                }
            });
            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { .. } = event {
                kill_server(&window.app_handle().clone());
            }
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if let RunEvent::ExitRequested { .. } = event {
                kill_server(app_handle);
            }
        });
}
