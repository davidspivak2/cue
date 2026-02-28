use std::{
    env,
    fs::{self, File},
    io::{self, Read, Write},
    net::{SocketAddr, TcpStream},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Mutex,
    },
    time::{Duration, SystemTime, UNIX_EPOCH},
};

#[cfg(windows)]
use std::os::windows::process::CommandExt;

use tauri::{path::BaseDirectory, App, AppHandle, Emitter, Manager, RunEvent, WindowEvent};

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;
use zip::ZipArchive;

const CALIBRATION_VIDEO_FILENAME: &str = "calibration_60s.mp4";
const ENGINE_PAYLOAD_FILENAME: &str = "engine_payload.zip";
const ENGINE_READY_SENTINEL: &str = ".extract-complete";
const ENGINE_PAYLOAD_METADATA_FILENAME: &str = ".payload-metadata";

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct PayloadMetadata {
    len: u64,
    modified_unix_seconds: u64,
}

fn read_payload_metadata(path: &Path) -> Option<PayloadMetadata> {
    let metadata = fs::metadata(path).ok()?;
    let modified_unix_seconds = metadata
        .modified()
        .ok()?
        .duration_since(UNIX_EPOCH)
        .ok()?
        .as_secs();
    Some(PayloadMetadata {
        len: metadata.len(),
        modified_unix_seconds,
    })
}

fn parse_payload_metadata(raw: &str) -> Option<PayloadMetadata> {
    let mut len: Option<u64> = None;
    let mut modified_unix_seconds: Option<u64> = None;
    for line in raw.lines() {
        if let Some(value) = line.strip_prefix("len=") {
            len = value.trim().parse::<u64>().ok();
        } else if let Some(value) = line.strip_prefix("modified_unix_seconds=") {
            modified_unix_seconds = value.trim().parse::<u64>().ok();
        }
    }
    Some(PayloadMetadata {
        len: len?,
        modified_unix_seconds: modified_unix_seconds?,
    })
}

fn read_cached_payload_metadata(path: &Path) -> Option<PayloadMetadata> {
    let raw = fs::read_to_string(path).ok()?;
    parse_payload_metadata(&raw)
}

fn write_cached_payload_metadata(path: &Path, metadata: PayloadMetadata) -> Result<(), String> {
    fs::write(
        path,
        format!(
            "len={}\nmodified_unix_seconds={}\n",
            metadata.len, metadata.modified_unix_seconds
        ),
    )
    .map_err(|err| format!("Failed to write payload metadata file {path:?}: {err}"))
}

fn cue_root_dir() -> PathBuf {
    if let Some(local_appdata) = env::var_os("LOCALAPPDATA") {
        return PathBuf::from(local_appdata).join("Cue");
    }
    if let Some(user_profile) = env::var_os("USERPROFILE") {
        return PathBuf::from(user_profile)
            .join("AppData")
            .join("Local")
            .join("Cue");
    }
    env::temp_dir().join("Cue")
}

fn cue_logs_dir() -> PathBuf {
    cue_root_dir().join("logs")
}

#[cfg(windows)]
fn cue_extra_dir() -> PathBuf {
    env::var_os("CUE_EXTRA")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("C:\\Cue_extra"))
}

fn cue_engine_root_dir() -> PathBuf {
    cue_root_dir().join("engine")
}

fn extract_zip_archive(zip_path: &Path, destination: &Path) -> Result<(), String> {
    let archive_file =
        File::open(zip_path).map_err(|err| format!("Failed to open engine payload {zip_path:?}: {err}"))?;
    let mut archive = ZipArchive::new(archive_file)
        .map_err(|err| format!("Failed to read engine payload archive {zip_path:?}: {err}"))?;

    for index in 0..archive.len() {
        let mut entry = archive
            .by_index(index)
            .map_err(|err| format!("Failed to read archive entry #{index}: {err}"))?;
        let Some(relative_path) = entry.enclosed_name() else {
            continue;
        };
        let output_path = destination.join(&relative_path);
        if entry.is_dir() {
            fs::create_dir_all(&output_path).map_err(|err| {
                format!("Failed to create extracted directory {output_path:?}: {err}")
            })?;
            continue;
        }
        if let Some(parent) = output_path.parent() {
            fs::create_dir_all(parent).map_err(|err| {
                format!("Failed to create extracted directory {parent:?}: {err}")
            })?;
        }
        let mut output_file = File::create(&output_path)
            .map_err(|err| format!("Failed to create extracted file {output_path:?}: {err}"))?;
        io::copy(&mut entry, &mut output_file)
            .map_err(|err| format!("Failed to extract file {output_path:?}: {err}"))?;
    }
    Ok(())
}

fn ensure_engine_extracted(app: &App) -> Result<PathBuf, String> {
    let payload_path = app
        .path()
        .resolve(ENGINE_PAYLOAD_FILENAME, BaseDirectory::Resource)
        .map_err(|err| format!("Failed to resolve engine payload resource path: {err}"))?;
    if !payload_path.exists() {
        return Err(format!("Engine payload archive missing: {payload_path:?}"));
    }

    let engine_root = cue_engine_root_dir();
    fs::create_dir_all(&engine_root)
        .map_err(|err| format!("Failed to create engine cache root {engine_root:?}: {err}"))?;

    let version = app.package_info().version.to_string();
    let extracted_engine_dir = engine_root.join(&version);
    let backend_path = extracted_engine_dir.join("CueBackend.exe");
    let ready_sentinel = extracted_engine_dir.join(ENGINE_READY_SENTINEL);
    let metadata_path = extracted_engine_dir.join(ENGINE_PAYLOAD_METADATA_FILENAME);
    let payload_metadata = read_payload_metadata(&payload_path);
    let cached_payload_metadata = read_cached_payload_metadata(&metadata_path);
    let has_cached_engine = backend_path.exists() && ready_sentinel.exists();
    if has_cached_engine && payload_metadata.is_some() && payload_metadata == cached_payload_metadata {
        return Ok(backend_path);
    }

    let unix_seconds = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs())
        .unwrap_or(0);
    let temp_engine_dir = engine_root.join(format!("{version}_tmp_{unix_seconds}"));
    if temp_engine_dir.exists() {
        let _ = fs::remove_dir_all(&temp_engine_dir);
    }
    fs::create_dir_all(&temp_engine_dir)
        .map_err(|err| format!("Failed to create temp engine directory {temp_engine_dir:?}: {err}"))?;

    if let Err(err) = extract_zip_archive(&payload_path, &temp_engine_dir) {
        let _ = fs::remove_dir_all(&temp_engine_dir);
        return Err(err);
    }

    let extracted_backend_path = temp_engine_dir.join("CueBackend.exe");
    if !extracted_backend_path.exists() {
        let _ = fs::remove_dir_all(&temp_engine_dir);
        return Err(format!(
            "Engine payload did not contain CueBackend.exe at root: {payload_path:?}"
        ));
    }
    if let Some(metadata) = payload_metadata {
        write_cached_payload_metadata(&temp_engine_dir.join(ENGINE_PAYLOAD_METADATA_FILENAME), metadata)?;
    }
    File::create(temp_engine_dir.join(ENGINE_READY_SENTINEL))
        .map_err(|err| format!("Failed to write engine extraction sentinel file: {err}"))?;

    if extracted_engine_dir.exists() {
        fs::remove_dir_all(&extracted_engine_dir).map_err(|err| {
            format!(
                "Failed to replace previous extracted engine directory {extracted_engine_dir:?}: {err}"
            )
        })?;
    }
    fs::rename(&temp_engine_dir, &extracted_engine_dir).map_err(|err| {
        format!(
            "Failed to activate extracted engine directory {temp_engine_dir:?} -> {extracted_engine_dir:?}: {err}"
        )
    })?;

    Ok(backend_path)
}

fn build_backend_log_path(logs_dir: &Path) -> PathBuf {
    let unix_seconds = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs())
        .unwrap_or(0);
    logs_dir.join(format!("backend_sidecar_{unix_seconds}.log"))
}

fn start_packaged_backend(app: &App) -> Option<Child> {
    let backend_path = match ensure_engine_extracted(app) {
        Ok(path) => path,
        Err(err) => {
            eprintln!("Failed to prepare packaged engine payload: {err}");
            return None;
        }
    };
    let engine_dir = backend_path.parent()?.to_path_buf();

    let logs_dir = cue_logs_dir();
    if let Err(err) = fs::create_dir_all(&logs_dir) {
        eprintln!("Failed to create backend logs directory {logs_dir:?}: {err}");
    }
    let log_path = build_backend_log_path(&logs_dir);

    let mut command = Command::new(&backend_path);
    command
        .current_dir(&engine_dir)
        .stdin(Stdio::null())
        .env("CUE_BACKEND_PORT", "8765");

    match File::create(&log_path) {
        Ok(stdout_file) => match stdout_file.try_clone() {
            Ok(stderr_file) => {
                command
                    .stdout(Stdio::from(stdout_file))
                    .stderr(Stdio::from(stderr_file));
            }
            Err(err) => {
                eprintln!("Failed to clone backend log handle {log_path:?}: {err}");
                command.stdout(Stdio::from(stdout_file)).stderr(Stdio::null());
            }
        },
        Err(err) => {
            eprintln!("Failed to create backend log file {log_path:?}: {err}");
            command.stdout(Stdio::null()).stderr(Stdio::null());
        }
    }

    #[cfg(windows)]
    command.creation_flags(CREATE_NO_WINDOW);

    match command.spawn() {
        Ok(child) => Some(child),
        Err(err) => {
            eprintln!("Failed to start packaged backend at {backend_path:?}: {err}");
            None
        }
    }
}

#[cfg(debug_assertions)]
fn repo_root_dir() -> PathBuf {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    manifest_dir
        .parent()
        .and_then(|path| path.parent())
        .map(Path::to_path_buf)
        .unwrap_or(manifest_dir)
}

#[cfg(debug_assertions)]
fn start_dev_backend(_app: &App) -> Option<Child> {
    let repo_root = repo_root_dir();
    let venv_python = repo_root.join(".venv").join("Scripts").join("python.exe");
    let mut command = if venv_python.exists() {
        Command::new(venv_python)
    } else {
        Command::new("python")
    };

    let logs_dir = cue_logs_dir();
    if let Err(err) = fs::create_dir_all(&logs_dir) {
        eprintln!("Failed to create backend logs directory {logs_dir:?}: {err}");
    }
    let log_path = build_backend_log_path(&logs_dir);

    command
        .arg("-m")
        .arg("app.backend_server")
        .current_dir(&repo_root)
        .stdin(Stdio::null())
        .env("CUE_BACKEND_PORT", "8765")
        .env("PYTHONUNBUFFERED", "1")
        .env("PYTHONIOENCODING", "utf-8");

    match File::create(&log_path) {
        Ok(stdout_file) => match stdout_file.try_clone() {
            Ok(stderr_file) => {
                command
                    .stdout(Stdio::from(stdout_file))
                    .stderr(Stdio::from(stderr_file));
            }
            Err(err) => {
                eprintln!("Failed to clone backend log handle {log_path:?}: {err}");
                command.stdout(Stdio::from(stdout_file)).stderr(Stdio::null());
            }
        },
        Err(err) => {
            eprintln!("Failed to create backend log file {log_path:?}: {err}");
            command.stdout(Stdio::null()).stderr(Stdio::null());
        }
    }

    #[cfg(windows)]
    command.creation_flags(CREATE_NO_WINDOW);

    match command.spawn() {
        Ok(child) => Some(child),
        Err(err) => {
            eprintln!(
                "Failed to start dev backend from repo {repo_root:?}: {err}. Falling back to packaged backend."
            );
            None
        }
    }
}

fn start_backend(app: &App) -> Option<Child> {
    #[cfg(debug_assertions)]
    {
        if let Some(child) = start_dev_backend(app) {
            return Some(child);
        }
    }
    start_packaged_backend(app)
}

fn wait_for_backend_listening(timeout: Duration, interval: Duration) {
    let addr = match "127.0.0.1:8765".parse::<SocketAddr>() {
        Ok(a) => a,
        Err(_) => return,
    };
    let deadline = SystemTime::now() + timeout;
    while SystemTime::now() < deadline {
        if TcpStream::connect_timeout(&addr, Duration::from_millis(500)).is_ok() {
            return;
        }
        std::thread::sleep(interval);
    }
}

fn request_backend_archive_on_exit() {
    let addr = match "127.0.0.1:8765".parse::<SocketAddr>() {
        Ok(value) => value,
        Err(_) => return,
    };
    let mut stream = match TcpStream::connect_timeout(&addr, Duration::from_millis(800)) {
        Ok(value) => value,
        Err(_) => return,
    };
    let _ = stream.set_write_timeout(Some(Duration::from_secs(2)));
    let _ = stream.set_read_timeout(Some(Duration::from_secs(20)));
    let request = "POST /diagnostics/archive-on-exit HTTP/1.1\r\nHost: 127.0.0.1:8765\r\nConnection: close\r\nContent-Length: 0\r\n\r\n";
    if stream.write_all(request.as_bytes()).is_err() {
        return;
    }
    let mut buffer = [0_u8; 1024];
    loop {
        match stream.read(&mut buffer) {
            Ok(0) => break,
            Ok(_) => {}
            Err(_) => break,
        }
    }
}

fn stop_backend_process(shared_child: &Arc<Mutex<Option<Child>>>) {
    request_backend_archive_on_exit();

    let mut guard = match shared_child.lock() {
        Ok(lock) => lock,
        Err(err) => {
            eprintln!("Failed to lock backend child state: {err}");
            return;
        }
    };

    let Some(child) = guard.as_mut() else {
        #[cfg(windows)]
        try_stop_dev_backend_by_pid_file();
        return;
    };

    match child.try_wait() {
        Ok(Some(_status)) => {
            *guard = None;
            return;
        }
        Ok(None) => {}
        Err(err) => {
            eprintln!("Failed to check backend process status: {err}");
        }
    }

    let pid = child.id();

    #[cfg(windows)]
    {
        let _ = Command::new("taskkill")
            .args(["/PID", &pid.to_string(), "/T", "/F"])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
    }

    #[cfg(not(windows))]
    if let Err(err) = child.kill() {
        eprintln!("Failed to terminate backend process: {err}");
    }
    #[cfg(windows)]
    let _ = child.kill();
    let _ = child.wait();
    *guard = None;
}

struct AllowCloseState(AtomicBool);
impl Default for AllowCloseState {
    fn default() -> Self {
        Self(AtomicBool::new(false))
    }
}

#[tauri::command]
fn get_calibration_video_path(app: AppHandle) -> Result<String, String> {
    let path = app
        .path()
        .resolve(CALIBRATION_VIDEO_FILENAME, BaseDirectory::Resource)
        .map_err(|e| format!("Failed to resolve calibration video path: {e}"))?;
    if !path.exists() {
        return Err(format!("Calibration video not found: {}", path.display()));
    }
    Ok(path.to_string_lossy().into_owned())
}

#[tauri::command]
fn allow_exit_and_close(app: AppHandle) -> Result<(), String> {
    app.try_state::<AllowCloseState>()
        .ok_or_else(|| "AllowCloseState not found".to_string())?
        .0
        .store(true, Ordering::Relaxed);
    let window = app
        .get_webview_window("main")
        .ok_or_else(|| "main window not found".to_string())?;
    window.close().map_err(|e| e.to_string())
}

#[cfg(windows)]
fn try_stop_dev_backend_by_pid_file() {
    let pid_path = cue_extra_dir().join("backend_pid.json");
    let Ok(contents) = fs::read_to_string(&pid_path) else {
        return;
    };
    let rest = contents.trim().strip_prefix("{\"pid\":").or_else(|| contents.trim().strip_prefix("{\"pid\": "));
    let pid: u32 = match rest.and_then(|s| s.trim().trim_end_matches('}').trim().parse().ok()) {
        Some(p) => p,
        None => return,
    };
    let _ = Command::new("taskkill")
        .args(["/PID", &pid.to_string(), "/T", "/F"])
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status();
    let _ = fs::remove_file(pid_path);
}

fn main() {
    let backend_child: Arc<Mutex<Option<Child>>> = Arc::new(Mutex::new(None));
    let backend_child_for_setup = Arc::clone(&backend_child);
    let backend_child_for_run = Arc::clone(&backend_child);

    let mut builder = tauri::Builder::default();
    #[cfg(debug_assertions)]
    {
        builder = builder.plugin(tauri_plugin_mcp_bridge::init());
    }
    builder
        .setup(move |app| {
            app.manage(AllowCloseState::default());
            if let Some(child) = start_backend(app) {
                match backend_child_for_setup.lock() {
                    Ok(mut lock) => {
                        *lock = Some(child);
                    }
                    Err(err) => {
                        eprintln!("Failed to store backend process handle: {err}");
                    }
                }
                wait_for_backend_listening(
                    Duration::from_secs(30),
                    Duration::from_millis(300),
                );
            }
            Ok(())
        })
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                if window.label() != "main" {
                    return;
                }
                let allow = window
                    .app_handle()
                    .try_state::<AllowCloseState>()
                    .map(|s| s.0.load(Ordering::Relaxed))
                    .unwrap_or(false);
                if !allow {
                    api.prevent_close();
                    let _ = window.app_handle().emit("close-requested", ());
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            get_calibration_video_path,
            allow_exit_and_close
        ])
        .build(tauri::generate_context!())
        .expect("error while running tauri application")
        .run(move |_app, event| {
            let should_stop = matches!(event, RunEvent::ExitRequested { .. } | RunEvent::Exit)
                || matches!(
                    event,
                    RunEvent::WindowEvent {
                        label,
                        event: WindowEvent::CloseRequested { .. },
                        ..
                    } if label == "main"
                );
            if should_stop {
                stop_backend_process(&backend_child_for_run);
            }
        });
}
