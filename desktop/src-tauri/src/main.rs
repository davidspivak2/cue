#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

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

use serde::{Deserialize, Serialize};
use tauri::{path::BaseDirectory, AppHandle, Emitter, Manager, RunEvent, WindowEvent};

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;
#[cfg(windows)]
use windows::Win32::{
    Foundation::{HWND, LPARAM, WPARAM},
    UI::WindowsAndMessaging::{
        CreateIcon, DestroyIcon, SendMessageW, HICON, ICON_BIG, ICON_SMALL, WM_SETICON,
    },
};
use zip::ZipArchive;

const CALIBRATION_VIDEO_FILENAME: &str = "calibration_60s.mp4";
const ENGINE_PARTS_MANIFEST_FILENAME: &str = "cue-engine-parts.json";
const ENGINE_READY_SENTINEL: &str = ".extract-complete";
const ENGINE_ARCHIVE_METADATA_FILENAME: &str = ".archive-metadata";

macro_rules! dev_eprintln {
    ($($arg:tt)*) => {
        #[cfg(debug_assertions)]
        eprintln!($($arg)*);
    };
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
struct EngineArchivesFingerprint {
    version: u32,
    parts: Vec<PartFileMetadata>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
struct PartFileMetadata {
    len: u64,
    modified_unix_seconds: u64,
}

#[derive(Deserialize)]
struct EnginePartsManifest {
    #[allow(dead_code)]
    version: u32,
    parts: Vec<EnginePartEntry>,
}

#[derive(Deserialize, Clone)]
struct EnginePartEntry {
    file: String,
    label: String,
}

#[derive(Clone, serde::Serialize)]
struct EngineExtractProgressPayload {
    label: String,
    index: u32,
    total: u32,
    phase: String,
}

fn strip_utf8_bom(s: &str) -> &str {
    s.strip_prefix('\u{feff}').unwrap_or(s)
}

fn read_cached_archives_fingerprint(path: &Path) -> Option<EngineArchivesFingerprint> {
    let raw = fs::read_to_string(path).ok()?;
    serde_json::from_str(strip_utf8_bom(raw.trim())).ok()
}

fn write_cached_archives_fingerprint(
    path: &Path,
    fingerprint: &EngineArchivesFingerprint,
) -> Result<(), String> {
    let json = serde_json::to_string_pretty(fingerprint)
        .map_err(|err| format!("Failed to serialize archive fingerprint: {err}"))?;
    fs::write(path, json)
        .map_err(|err| format!("Failed to write archive metadata file {path:?}: {err}"))
}

fn fingerprint_for_zip_paths(paths: &[PathBuf]) -> Result<EngineArchivesFingerprint, String> {
    let mut parts = Vec::new();
    for path in paths {
        let metadata = read_part_file_metadata(path)
            .ok_or_else(|| format!("Failed to read engine part metadata for {}", path.display()))?;
        parts.push(metadata);
    }
    Ok(EngineArchivesFingerprint { version: 1, parts })
}

fn read_part_file_metadata(path: &Path) -> Option<PartFileMetadata> {
    let metadata = fs::metadata(path).ok()?;
    let modified_unix_seconds = metadata
        .modified()
        .ok()?
        .duration_since(UNIX_EPOCH)
        .ok()?
        .as_secs();
    Some(PartFileMetadata {
        len: metadata.len(),
        modified_unix_seconds,
    })
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
    let archive_file = File::open(zip_path)
        .map_err(|err| format!("Failed to open engine archive {zip_path:?}: {err}"))?;
    let mut archive = ZipArchive::new(archive_file)
        .map_err(|err| format!("Failed to read engine archive {zip_path:?}: {err}"))?;

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
            fs::create_dir_all(parent)
                .map_err(|err| format!("Failed to create extracted directory {parent:?}: {err}"))?;
        }
        let mut output_file = File::create(&output_path)
            .map_err(|err| format!("Failed to create extracted file {output_path:?}: {err}"))?;
        io::copy(&mut entry, &mut output_file)
            .map_err(|err| format!("Failed to extract file {output_path:?}: {err}"))?;
    }
    Ok(())
}

fn emit_engine_extract_progress(app: &AppHandle, payload: EngineExtractProgressPayload) {
    let _ = app.emit("engine-extract-progress", &payload);
}

fn ensure_engine_extracted(app: &AppHandle) -> Result<PathBuf, String> {
    let manifest_path = app
        .path()
        .resolve(ENGINE_PARTS_MANIFEST_FILENAME, BaseDirectory::Resource)
        .map_err(|err| format!("Failed to resolve engine parts manifest path: {err}"))?;
    if !manifest_path.exists() {
        return Err(format!("Engine parts manifest missing: {manifest_path:?}"));
    }

    let manifest_raw = fs::read_to_string(&manifest_path)
        .map_err(|err| format!("Failed to read engine parts manifest {manifest_path:?}: {err}"))?;
    let manifest_json = strip_utf8_bom(manifest_raw.trim());
    let manifest: EnginePartsManifest = serde_json::from_str(manifest_json)
        .map_err(|err| format!("Failed to parse engine parts manifest {manifest_path:?}: {err}"))?;

    if manifest.parts.is_empty() {
        return Err("Engine parts manifest lists no archives".to_string());
    }

    let mut zip_paths: Vec<PathBuf> = Vec::new();
    for part in &manifest.parts {
        let zip_path = app
            .path()
            .resolve(&part.file, BaseDirectory::Resource)
            .map_err(|err| format!("Failed to resolve engine part {}: {err}", part.file))?;
        if !zip_path.exists() {
            return Err(format!("Engine part archive missing: {zip_path:?}"));
        }
        zip_paths.push(zip_path);
    }

    let archives_fingerprint = fingerprint_for_zip_paths(&zip_paths)?;

    let engine_root = cue_engine_root_dir();
    fs::create_dir_all(&engine_root)
        .map_err(|err| format!("Failed to create engine cache root {engine_root:?}: {err}"))?;

    let version = app.package_info().version.to_string();
    let extracted_engine_dir = engine_root.join(&version);
    let backend_path = extracted_engine_dir.join("CueBackend.exe");
    let ready_sentinel = extracted_engine_dir.join(ENGINE_READY_SENTINEL);
    let metadata_path = extracted_engine_dir.join(ENGINE_ARCHIVE_METADATA_FILENAME);
    let cached_fingerprint = read_cached_archives_fingerprint(&metadata_path);
    let has_cached_engine = backend_path.exists() && ready_sentinel.exists();
    if has_cached_engine && cached_fingerprint.as_ref() == Some(&archives_fingerprint) {
        return Ok(backend_path);
    }

    let total = manifest.parts.len() as u32;
    let unix_seconds = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs())
        .unwrap_or(0);
    let temp_engine_dir = engine_root.join(format!("{version}_tmp_{unix_seconds}"));
    if temp_engine_dir.exists() {
        let _ = fs::remove_dir_all(&temp_engine_dir);
    }
    fs::create_dir_all(&temp_engine_dir).map_err(|err| {
        format!("Failed to create temp engine directory {temp_engine_dir:?}: {err}")
    })?;

    for (index, (zip_path, part)) in zip_paths.iter().zip(manifest.parts.iter()).enumerate() {
        let i = index as u32 + 1;
        emit_engine_extract_progress(
            app,
            EngineExtractProgressPayload {
                label: part.label.clone(),
                index: i,
                total,
                phase: "start".to_string(),
            },
        );
        if let Err(err) = extract_zip_archive(zip_path, &temp_engine_dir) {
            let _ = fs::remove_dir_all(&temp_engine_dir);
            emit_engine_extract_progress(
                app,
                EngineExtractProgressPayload {
                    label: part.label.clone(),
                    index: i,
                    total,
                    phase: "error".to_string(),
                },
            );
            return Err(err);
        }
        emit_engine_extract_progress(
            app,
            EngineExtractProgressPayload {
                label: part.label.clone(),
                index: i,
                total,
                phase: "part_done".to_string(),
            },
        );
    }

    emit_engine_extract_progress(
        app,
        EngineExtractProgressPayload {
            label: "Almost ready...".to_string(),
            index: total,
            total,
            phase: "done".to_string(),
        },
    );

    let extracted_backend_path = temp_engine_dir.join("CueBackend.exe");
    if !extracted_backend_path.exists() {
        let _ = fs::remove_dir_all(&temp_engine_dir);
        return Err(
            "Engine archives did not produce CueBackend.exe at the expected root path".to_string(),
        );
    }

    write_cached_archives_fingerprint(
        &temp_engine_dir.join(ENGINE_ARCHIVE_METADATA_FILENAME),
        &archives_fingerprint,
    )?;
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

fn start_packaged_backend(app: &AppHandle) -> Option<Child> {
    let backend_path = match ensure_engine_extracted(app) {
        Ok(path) => path,
        Err(err) => {
            dev_eprintln!("Failed to prepare packaged engine archive: {err}");
            let _ = app.emit(
                "engine-extract-progress",
                &EngineExtractProgressPayload {
                    label: format!("Could not prepare engine: {err}"),
                    index: 0,
                    total: 0,
                    phase: "error".to_string(),
                },
            );
            return None;
        }
    };
    let engine_dir = backend_path.parent()?.to_path_buf();

    let logs_dir = cue_logs_dir();
    if let Err(err) = fs::create_dir_all(&logs_dir) {
        dev_eprintln!("Failed to create backend logs directory {logs_dir:?}: {err}");
        #[cfg(not(debug_assertions))]
        let _ = err;
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
                dev_eprintln!("Failed to clone backend log handle {log_path:?}: {err}");
                #[cfg(not(debug_assertions))]
                let _ = err;
                command
                    .stdout(Stdio::from(stdout_file))
                    .stderr(Stdio::null());
            }
        },
        Err(err) => {
            dev_eprintln!("Failed to create backend log file {log_path:?}: {err}");
            #[cfg(not(debug_assertions))]
            let _ = err;
            command.stdout(Stdio::null()).stderr(Stdio::null());
        }
    }

    #[cfg(windows)]
    command.creation_flags(CREATE_NO_WINDOW);

    match command.spawn() {
        Ok(child) => Some(child),
        Err(err) => {
            dev_eprintln!("Failed to start packaged backend at {backend_path:?}: {err}");
            #[cfg(not(debug_assertions))]
            let _ = err;
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
fn start_dev_backend(_app: &tauri::App) -> Option<Child> {
    let repo_root = repo_root_dir();
    let venv_python = repo_root.join(".venv").join("Scripts").join("python.exe");
    let mut command = if venv_python.exists() {
        Command::new(venv_python)
    } else {
        Command::new("python")
    };

    let logs_dir = cue_logs_dir();
    if let Err(err) = fs::create_dir_all(&logs_dir) {
        dev_eprintln!("Failed to create backend logs directory {logs_dir:?}: {err}");
        #[cfg(not(debug_assertions))]
        let _ = err;
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
                dev_eprintln!("Failed to clone backend log handle {log_path:?}: {err}");
                #[cfg(not(debug_assertions))]
                let _ = err;
                command
                    .stdout(Stdio::from(stdout_file))
                    .stderr(Stdio::null());
            }
        },
        Err(err) => {
            dev_eprintln!("Failed to create backend log file {log_path:?}: {err}");
            #[cfg(not(debug_assertions))]
            let _ = err;
            command.stdout(Stdio::null()).stderr(Stdio::null());
        }
    }

    #[cfg(windows)]
    command.creation_flags(CREATE_NO_WINDOW);

    match command.spawn() {
        Ok(child) => Some(child),
        Err(err) => {
            dev_eprintln!(
                "Failed to start dev backend from repo {repo_root:?}: {err}. Falling back to packaged backend."
            );
            #[cfg(not(debug_assertions))]
            let _ = err;
            None
        }
    }
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
            dev_eprintln!("Failed to lock backend child state: {err}");
            #[cfg(not(debug_assertions))]
            let _ = err;
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
            dev_eprintln!("Failed to check backend process status: {err}");
            #[cfg(not(debug_assertions))]
            let _ = err;
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
            .creation_flags(CREATE_NO_WINDOW)
            .status();
    }

    #[cfg(not(windows))]
    if let Err(err) = child.kill() {
        dev_eprintln!("Failed to terminate backend process: {err}");
        #[cfg(not(debug_assertions))]
        let _ = err;
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

#[cfg(windows)]
#[derive(Default)]
struct ThemeTaskbarIconState(Mutex<ThemeTaskbarIconHandles>);

#[cfg(windows)]
#[derive(Default)]
struct ThemeTaskbarIconHandles {
    small: Option<isize>,
    big: Option<isize>,
}

#[cfg(windows)]
fn resolve_theme_icon_path(app: &AppHandle, icon_name: &str, size: u32) -> Result<PathBuf, String> {
    let relative = format!("icons/{icon_name}-{size}.png");
    let bundled = app
        .path()
        .resolve(&relative, BaseDirectory::Resource)
        .map_err(|err| format!("Failed to resolve bundled theme icon {relative}: {err}"))?;
    if bundled.exists() {
        return Ok(bundled);
    }

    #[cfg(debug_assertions)]
    {
        let dev_path = repo_root_dir()
            .join("desktop")
            .join("public")
            .join("icons")
            .join(format!("{icon_name}-{size}.png"));
        if dev_path.exists() {
            return Ok(dev_path);
        }
    }

    Err(format!("Theme icon asset is missing: {relative}"))
}

#[cfg(windows)]
fn destroy_theme_icon(raw: isize) {
    if raw != 0 {
        let _ = unsafe { DestroyIcon(HICON(raw as _)) };
    }
}

#[cfg(windows)]
fn create_theme_icon_handle(path: &Path) -> Result<HICON, String> {
    let image = tauri::image::Image::from_path(path)
        .map_err(|err| format!("Failed to load theme icon {}: {err}", path.display()))?;
    let mut rgba = image.rgba().to_vec();
    let pixel_count = rgba.len() / 4;
    let mut and_mask = Vec::with_capacity(pixel_count);
    for pixel in rgba.chunks_exact_mut(4) {
        and_mask.push(pixel[3].wrapping_sub(u8::MAX));
        pixel.swap(0, 2);
    }

    unsafe {
        CreateIcon(
            None,
            image.width() as i32,
            image.height() as i32,
            1,
            32,
            and_mask.as_ptr(),
            rgba.as_ptr(),
        )
        .map_err(|_| {
            format!(
                "Failed to create Windows icon handle from {}: {}",
                path.display(),
                io::Error::last_os_error()
            )
        })
    }
}

#[cfg(windows)]
fn replace_theme_icon_handles(app: &AppHandle, small: HICON, big: HICON) -> Result<(), String> {
    let state = app
        .try_state::<ThemeTaskbarIconState>()
        .ok_or_else(|| "ThemeTaskbarIconState not found".to_string())?;
    let (old_small, old_big) = {
        let mut guard = state
            .0
            .lock()
            .map_err(|err| format!("Failed to lock theme icon state: {err}"))?;
        (
            guard.small.replace(small.0 as isize),
            guard.big.replace(big.0 as isize),
        )
    };
    if let Some(raw) = old_small {
        destroy_theme_icon(raw);
    }
    if let Some(raw) = old_big {
        destroy_theme_icon(raw);
    }
    Ok(())
}

#[cfg(windows)]
fn clear_theme_icon_handles(app: &AppHandle) {
    let Some(state) = app.try_state::<ThemeTaskbarIconState>() else {
        return;
    };
    let (small, big) = match state.0.lock() {
        Ok(mut guard) => (guard.small.take(), guard.big.take()),
        Err(err) => {
            dev_eprintln!("Failed to lock theme icon state during cleanup: {err}");
            return;
        }
    };
    if let Some(raw) = small {
        destroy_theme_icon(raw);
    }
    if let Some(raw) = big {
        destroy_theme_icon(raw);
    }
}

#[cfg(windows)]
fn apply_theme_taskbar_icon(window: &tauri::WebviewWindow) -> Result<(), String> {
    let icon_name = if matches!(window.theme(), Ok(tauri::Theme::Dark)) {
        "dark"
    } else {
        "light"
    };
    let app = window.app_handle();
    let small_path = resolve_theme_icon_path(&app, icon_name, 32)?;
    let big_path = resolve_theme_icon_path(&app, icon_name, 256)?;
    let small = create_theme_icon_handle(&small_path)?;
    let big = match create_theme_icon_handle(&big_path) {
        Ok(handle) => handle,
        Err(err) => {
            destroy_theme_icon(small.0 as isize);
            return Err(err);
        }
    };
    let hwnd: HWND = match window.hwnd() {
        Ok(handle) => handle,
        Err(err) => {
            destroy_theme_icon(small.0 as isize);
            destroy_theme_icon(big.0 as isize);
            return Err(format!("Failed to read main window handle: {err}"));
        }
    };

    unsafe {
        SendMessageW(
            hwnd,
            WM_SETICON,
            Some(WPARAM(ICON_SMALL as usize)),
            Some(LPARAM(small.0 as isize)),
        );
        SendMessageW(
            hwnd,
            WM_SETICON,
            Some(WPARAM(ICON_BIG as usize)),
            Some(LPARAM(big.0 as isize)),
        );
    }

    if let Err(err) = replace_theme_icon_handles(&app, small, big) {
        destroy_theme_icon(small.0 as isize);
        destroy_theme_icon(big.0 as isize);
        return Err(err);
    }

    Ok(())
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
    let rest = contents
        .trim()
        .strip_prefix("{\"pid\":")
        .or_else(|| contents.trim().strip_prefix("{\"pid\": "));
    let pid: u32 = match rest.and_then(|s| s.trim().trim_end_matches('}').trim().parse().ok()) {
        Some(p) => p,
        None => return,
    };
    let _ = Command::new("taskkill")
        .args(["/PID", &pid.to_string(), "/T", "/F"])
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .creation_flags(CREATE_NO_WINDOW)
        .status();
    let _ = fs::remove_file(pid_path);
}

fn main() {
    let backend_child: Arc<Mutex<Option<Child>>> = Arc::new(Mutex::new(None));
    let backend_child_for_setup = Arc::clone(&backend_child);
    let backend_child_for_run = Arc::clone(&backend_child);

    let builder = tauri::Builder::default();
    #[cfg(debug_assertions)]
    let builder = builder.plugin(tauri_plugin_mcp_bridge::init());
    builder
        .setup(move |app| {
            app.manage(AllowCloseState::default());
            #[cfg(windows)]
            app.manage(ThemeTaskbarIconState::default());
            let child_holder = Arc::clone(&backend_child_for_setup);

            #[cfg(windows)]
            {
                if let Some(main_window) = app.get_webview_window("main") {
                    if let Err(err) = apply_theme_taskbar_icon(&main_window) {
                        dev_eprintln!("Failed to apply initial Windows theme icon: {err}");
                    }
                }
            }

            #[cfg(debug_assertions)]
            {
                if let Some(child) = start_dev_backend(app) {
                    match child_holder.lock() {
                        Ok(mut lock) => {
                            *lock = Some(child);
                        }
                        Err(err) => {
                            dev_eprintln!("Failed to store backend process handle: {err}");
                            #[cfg(not(debug_assertions))]
                            let _ = err;
                        }
                    }
                    wait_for_backend_listening(Duration::from_secs(30), Duration::from_millis(300));
                    return Ok(());
                }
            }

            let handle = app.handle().clone();
            if let Err(err) = std::thread::Builder::new()
                .name("cue-backend".into())
                .spawn(move || {
                    if let Some(child) = start_packaged_backend(&handle) {
                        if let Ok(mut guard) = child_holder.lock() {
                            *guard = Some(child);
                        }
                        wait_for_backend_listening(
                            Duration::from_secs(120),
                            Duration::from_millis(300),
                        );
                    }
                })
            {
                dev_eprintln!("Failed to spawn packaged backend thread: {err}");
                #[cfg(not(debug_assertions))]
                let _ = err;
            }

            Ok(())
        })
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .on_window_event(|window, event| match event {
            WindowEvent::CloseRequested { api, .. } => {
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
            #[cfg(windows)]
            WindowEvent::ThemeChanged(_) => {
                if window.label() == "main" {
                    if let Some(main_window) = window.app_handle().get_webview_window("main") {
                        if let Err(err) = apply_theme_taskbar_icon(&main_window) {
                            dev_eprintln!("Failed to update Windows theme icon: {err}");
                        }
                    }
                }
            }
            _ => {}
        })
        .invoke_handler(tauri::generate_handler![
            get_calibration_video_path,
            allow_exit_and_close
        ])
        .build(tauri::generate_context!())
        .expect("error while running tauri application")
        .run(move |app, event| {
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
                #[cfg(windows)]
                clear_theme_icon_handles(app);
                stop_backend_process(&backend_child_for_run);
            }
        });
}
