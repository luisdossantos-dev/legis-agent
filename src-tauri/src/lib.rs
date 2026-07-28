// Legis Agent — Tauri Commands
// Functions invocable from the React frontend

use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::Duration;
use tauri::Manager;
use tauri::WindowEvent;

// ── Sidecar Manager ─────────────────────────────────────────

struct BackendProcess(Mutex<Option<Child>>);

/// Resolve the project root directory by walking up from the
/// Tauri binary location until we find the `backend` folder.
fn find_project_root() -> Option<PathBuf> {
    // Start from the executable's directory
    let mut path = std::env::current_exe().ok()?;
    path.pop(); // remove executable name

    // Walk up looking for the backend directory
    for _ in 0..5 {
        if path.join("backend").is_dir() {
            return Some(path);
        }
        path.pop();
    }
    None
}

/// Try to find the uvicorn executable inside the backend venv.
fn find_uvicorn() -> Option<PathBuf> {
    let root = find_project_root()?;

    // Check common venv locations
    for venv_python in &[
        root.join("backend/.venv/bin/uvicorn"),
        root.join("backend/.venv/Scripts/uvicorn.exe"),
        root.join("backend/venv/bin/uvicorn"),
        root.join("backend/venv/Scripts/uvicorn.exe"),
    ] {
        if venv_python.exists() {
            return Some(venv_python.clone());
        }
    }

    // Fallback: check if uvicorn is in PATH
    if Command::new("uvicorn")
        .arg("--version")
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .spawn()
        .is_ok()
    {
        return Some(PathBuf::from("uvicorn"));
    }

    None
}

#[tauri::command]
async fn check_backend_status() -> Result<String, String> {
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(3))
        .build()
        .map_err(|e| e.to_string())?;

    let resp = client
        .get("http://localhost:8000/health")
        .send()
        .await
        .map_err(|_| "Backend unavailable".to_string())?;

    if resp.status().is_success() {
        Ok("online".to_string())
    } else {
        Ok("offline".to_string())
    }
}

#[tauri::command]
async fn get_backend_url() -> String {
    "http://localhost:8000".to_string()
}

fn is_port_in_use(port: u16) -> bool {
    use std::net::TcpStream;
    TcpStream::connect_timeout(
        &format!("127.0.0.1:{}", port).parse().unwrap(),
        std::time::Duration::from_millis(500),
    )
    .is_ok()
}

fn start_backend() -> Option<Child> {
    // Check if backend is already running
    if is_port_in_use(8000) {
        println!("✅ Backend already running on port 8000");
        return None;
    }

    let uvicorn = find_uvicorn()?;
    let root = find_project_root()?;
    let backend_dir = root.join("backend");

    println!(
        "Starting backend: {} in {}",
        uvicorn.display(),
        backend_dir.display()
    );

    match Command::new(&uvicorn)
        .args(["app.main:app", "--host", "0.0.0.0", "--port", "8000"])
        .current_dir(&backend_dir)
        .spawn()
    {
        Ok(child) => {
            println!("✅ Python backend started (PID: {})", child.id());
            Some(child)
        }
        Err(e) => {
            eprintln!("⚠️ Could not start backend: {}", e);
            eprintln!("   Run it manually: cd backend && uvicorn app.main:app");
            None
        }
    }
}

// ── Entry Point ─────────────────────────────────────────────

pub fn run() {
    // Start backend (no-op if already running)
    let backend_child = start_backend();

    tauri::Builder::default()
        .manage(BackendProcess(Mutex::new(backend_child)))
        .invoke_handler(tauri::generate_handler![
            check_backend_status,
            get_backend_url,
        ])
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { .. } = event {
                // Kill backend on window close
                if let Some(state) = window.try_state::<BackendProcess>() {
                    if let Ok(mut guard) = state.0.lock() {
                        if let Some(ref mut child) = *guard {
                            let _ = child.kill();
                            println!("👋 Backend stopped");
                        }
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("Error starting Legis Agent");
}
