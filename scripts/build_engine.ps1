$ErrorActionPreference = "Stop"
Set-StrictMode -Version 3

$repo = Split-Path $PSScriptRoot -Parent
Set-Location $repo

$venvPython = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "[INFO] Creating virtual environment..."
    & python -m venv ".venv"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create virtual environment."
    }
}

if (-not (Test-Path $venvPython)) {
    throw "Virtual environment python not found at $venvPython"
}

Write-Host "[INFO] Installing/refreshing Python dependencies..."
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Failed to upgrade pip."
}

& $venvPython -m pip install -r "requirements.txt"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install requirements."
}

& $venvPython -m pip show pyinstaller *> $null
if ($LASTEXITCODE -ne 0) {
    & $venvPython -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install PyInstaller."
    }
}

$binDir = Join-Path $repo "bin"
if (-not (Test-Path $binDir)) {
    New-Item -ItemType Directory -Path $binDir | Out-Null
}

$ffmpegTarget = Join-Path $binDir "ffmpeg.exe"
$ffprobeTarget = Join-Path $binDir "ffprobe.exe"

if (-not (Test-Path $ffmpegTarget)) {
    $ffmpegCommand = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if ($ffmpegCommand) {
        Copy-Item -Force $ffmpegCommand.Source $ffmpegTarget
    }
}

if (-not (Test-Path $ffprobeTarget)) {
    $ffprobeCommand = Get-Command ffprobe -ErrorAction SilentlyContinue
    if ($ffprobeCommand) {
        Copy-Item -Force $ffprobeCommand.Source $ffprobeTarget
    }
}

if (-not (Test-Path $ffmpegTarget) -or -not (Test-Path $ffprobeTarget)) {
    Write-Host "[INFO] Downloading FFmpeg binaries..."
    & (Join-Path $repo "scripts\download_ffmpeg.bat")
    if ($LASTEXITCODE -ne 0) {
        throw "download_ffmpeg.bat failed."
    }
}

if (-not (Test-Path $ffmpegTarget)) {
    throw "FFmpeg is missing at $ffmpegTarget"
}
if (-not (Test-Path $ffprobeTarget)) {
    throw "FFprobe is missing at $ffprobeTarget"
}

$engineSpec = Join-Path $repo "CueEngine.spec"
$engineBuildDir = Join-Path $repo "build\CueEngine"
$engineDistDir = Join-Path $repo "dist\CueEngine"
$engineTemplate = Join-Path $repo "tools\pyinstaller.engine.spec.in"
$engineArchiveFileName = "cue-local-engine.zip"
$engineArchivePath = Join-Path $repo (Join-Path "desktop\src-tauri" $engineArchiveFileName)
$engineArchiveDirectory = Split-Path $engineArchivePath -Parent

if (Test-Path $engineSpec) {
    Remove-Item -Force $engineSpec
}
if (Test-Path $engineBuildDir) {
    Remove-Item -Recurse -Force $engineBuildDir
}
if (Test-Path $engineDistDir) {
    Remove-Item -Recurse -Force $engineDistDir
}

Copy-Item -Force $engineTemplate $engineSpec

Write-Host "[INFO] Running PyInstaller for engine..."
& $venvPython -m PyInstaller --noconfirm $engineSpec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed."
}

$requiredExes = @(
    "CueBackend.exe",
    "CueRunner.exe",
    "CueWorker.exe",
    "CueAlignWorker.exe"
)
foreach ($exeName in $requiredExes) {
    $exePath = Join-Path $engineDistDir $exeName
    if (-not (Test-Path $exePath)) {
        throw "Missing $exePath after build."
    }
}

$internalRoot = Join-Path $engineDistDir "_internal"
$openMpCandidates = @(
    (Join-Path $internalRoot "ctranslate2\libiomp5md.dll"),
    (Join-Path $internalRoot "torch\lib\libiomp5md.dll")
)
$openMpSource = $openMpCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($openMpSource) {
    $openMpTarget = Join-Path $internalRoot "libiomp5md.dll"
    Copy-Item -Force $openMpSource $openMpTarget
    foreach ($candidate in $openMpCandidates) {
        if (Test-Path $candidate) {
            Remove-Item -Force $candidate
        }
    }
    Write-Host "[INFO] Normalized OpenMP runtime to $openMpTarget"
}

if (-not (Test-Path $engineArchiveDirectory)) {
    throw "Engine archive directory is missing at $engineArchiveDirectory"
}

if (Test-Path $engineArchivePath) {
    Remove-Item -Force $engineArchivePath
}
Write-Host "[INFO] Creating engine archive at $engineArchivePath"
Compress-Archive -Path (Join-Path $engineDistDir "*") -DestinationPath $engineArchivePath -CompressionLevel Optimal
if (-not (Test-Path $engineArchivePath)) {
    throw "Engine archive was not created: $engineArchivePath"
}
$archiveSizeBytes = (Get-Item $engineArchivePath).Length
Write-Host ("[INFO] Engine archive size: {0:N0} bytes ({1:N2} MB)" -f $archiveSizeBytes, ($archiveSizeBytes / 1MB))

Write-Host "[OK] Engine build complete."
Write-Host "[OK] Engine archive: $engineArchivePath"
