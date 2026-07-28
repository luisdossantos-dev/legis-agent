// Legis Agent — Tauri Backend (Rust)
// Entry point: lanza webview + sidecar Python

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    legis_agent::run();
}
