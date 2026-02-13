use std::{
    env,
    fs::{self, File},
    io,
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::{Arc, Mutex},
    time::{SystemTime, UNIX_EPOCH},
};

use tauri::{path::BaseDirectory, App, Manager, RunEvent};
use zip::ZipArchive;

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

    match command.spawn() {
        Ok(child) => Some(child),
        Err(err) => {
            eprintln!("Failed to start packaged backend at {backend_path:?}: {err}");
            None
        }
    }
}

fn stop_backend_process(shared_child: &Arc<Mutex<Option<Child>>>) {
    let mut guard = match shared_child.lock() {
        Ok(lock) => lock,
        Err(err) => {
            eprintln!("Failed to lock backend child state: {err}");
            return;
        }
    };

    let Some(child) = guard.as_mut() else {
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

    if let Err(err) = child.kill() {
        eprintln!("Failed to terminate backend process: {err}");
    }
    let _ = child.wait();
    *guard = None;
}

fn main() {
    let backend_child: Arc<Mutex<Option<Child>>> = Arc::new(Mutex::new(None));
    let backend_child_for_setup = Arc::clone(&backend_child);
    let backend_child_for_run = Arc::clone(&backend_child);

    tauri::Builder::default()
        .setup(move |app| {
            if let Some(child) = start_packaged_backend(app) {
                match backend_child_for_setup.lock() {
                    Ok(mut lock) => {
                        *lock = Some(child);
                    }
                    Err(err) => {
                        eprintln!("Failed to store backend process handle: {err}");
                    }
                }
            }
            Ok(())
        })
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .build(tauri::generate_context!())
        .expect("error while running tauri application")
        .run(move |_app, event| {
            if matches!(event, RunEvent::ExitRequested { .. } | RunEvent::Exit) {
                stop_backend_process(&backend_child_for_run);
            }
        });
}
