$ErrorActionPreference = "Stop"
Set-StrictMode -Version 3

function Get-DirectorySizeBytes {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        return 0
    }

    $measure = Get-ChildItem -Path $Path -Recurse -File -ErrorAction SilentlyContinue |
        Measure-Object -Property Length -Sum
    if ($null -eq $measure.Sum) {
        return 0
    }
    return [int64]$measure.Sum
}

function Remove-EngineRuntimePath {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        return $false
    }

    Remove-Item -Recurse -Force $Path
    return $true
}

function Remove-EngineRuntimeGlob {
    param([string]$Path)

    $items = @(Get-ChildItem -Path $Path -Force -ErrorAction SilentlyContinue)
    foreach ($item in $items) {
        Remove-Item -Recurse -Force $item.FullName
    }
    return $items.Count
}

function Remove-EngineRuntimeLibFiles {
    param([string]$RootPath)

    if (-not (Test-Path $RootPath)) {
        return @()
    }

    $libFiles = Get-ChildItem -Path $RootPath -Recurse -Filter "*.lib" -File -ErrorAction SilentlyContinue
    foreach ($file in $libFiles) {
        Remove-Item -Force $file.FullName
    }
    return $libFiles
}

function Assert-NoEngineRuntimeLibFiles {
    param([string]$RootPath)

    $remaining = Get-ChildItem -Path $RootPath -Recurse -Filter "*.lib" -File -ErrorAction SilentlyContinue
    if ($remaining) {
        $samplePaths = $remaining | Select-Object -First 20 -ExpandProperty FullName
        throw "Packaged engine still contains .lib runtime files:`n$($samplePaths -join "`n")"
    }
}

function Remove-MatchingRuntimeDuplicateFile {
    param(
        [string]$PrimaryPath,
        [string]$DuplicatePath
    )

    if (-not (Test-Path $PrimaryPath) -or -not (Test-Path $DuplicatePath)) {
        return $false
    }

    $primaryHash = (Get-FileHash -Path $PrimaryPath -Algorithm SHA256).Hash
    $duplicateHash = (Get-FileHash -Path $DuplicatePath -Algorithm SHA256).Hash
    if ($primaryHash -ne $duplicateHash) {
        Write-Host "[WARN] Skipping duplicate prune because hashes differ: $DuplicatePath"
        return $false
    }

    Remove-Item -Force $DuplicatePath
    return $true
}

function Remove-OptionalPySide6Payload {
    param([string]$InternalRoot)

    $removed = @()
    $qtRoot = Join-Path $InternalRoot "PySide6"
    if (-not (Test-Path $qtRoot)) {
        return $removed
    }

    foreach ($relativePath in @(
        "Qt6Quick.dll",
        "Qt6Pdf.dll",
        "Qt6Qml.dll",
        "Qt6QmlModels.dll",
        "Qt6Svg.dll",
        "Qt6Network.dll",
        "Qt6OpenGL.dll",
        "Qt6VirtualKeyboard.dll",
        "QtNetwork.pyd",
        "opengl32sw.dll",
        "plugins\generic\qtuiotouchplugin.dll",
        "plugins\iconengines\qsvgicon.dll",
        "plugins\platforminputcontexts",
        "plugins\networkinformation",
        "plugins\tls",
        "plugins\styles\qmodernwindowsstyle.dll",
        "plugins\platforms\qdirect2d.dll",
        "translations"
    )) {
        $fullPath = Join-Path $qtRoot $relativePath
        if (Remove-EngineRuntimePath -Path $fullPath) {
            $removed += $fullPath
        }
    }

    $platformsDir = Join-Path $qtRoot "plugins\platforms"
    if (Test-Path $platformsDir) {
        foreach ($platformPlugin in Get-ChildItem -Path $platformsDir -File -ErrorAction SilentlyContinue) {
            if ($platformPlugin.Name -notin @("qwindows.dll", "qoffscreen.dll")) {
                Remove-Item -Force $platformPlugin.FullName
                $removed += $platformPlugin.FullName
            }
        }
    }

    $imageFormatsDir = Join-Path $qtRoot "plugins\imageformats"
    if (Test-Path $imageFormatsDir) {
        foreach ($imagePlugin in Get-ChildItem -Path $imageFormatsDir -File -ErrorAction SilentlyContinue) {
            if ($imagePlugin.Name -notin @("qjpeg.dll", "qpng.dll")) {
                Remove-Item -Force $imagePlugin.FullName
                $removed += $imagePlugin.FullName
            }
        }
    }

    return $removed
}

function Remove-OptionalPillowRuntimePayload {
    param([string]$InternalRoot)

    $removed = @()
    $pillowRoot = Join-Path $InternalRoot "PIL"
    if (-not (Test-Path $pillowRoot)) {
        return $removed
    }

    $avifPluginPath = Join-Path $pillowRoot "_avif.cp311-win_amd64.pyd"
    if (Remove-EngineRuntimePath -Path $avifPluginPath) {
        $removed += $avifPluginPath
    }

    return $removed
}

function Remove-OptionalTorchRuntimePayload {
    param([string]$InternalRoot)

    $removed = @()
    $torchRoot = Join-Path $InternalRoot "torch"
    if (-not (Test-Path $torchRoot)) {
        return $removed
    }

    $protocPath = Join-Path $torchRoot "bin\protoc.exe"
    if (Remove-EngineRuntimePath -Path $protocPath) {
        $removed += $protocPath
    }

    if (Remove-MatchingRuntimeDuplicateFile `
        -PrimaryPath (Join-Path $torchRoot "lib\fbgemm.dll") `
        -DuplicatePath (Join-Path $torchRoot "bin\fbgemm.dll")) {
        $removed += (Join-Path $torchRoot "bin\fbgemm.dll")
    }

    if (Remove-MatchingRuntimeDuplicateFile `
        -PrimaryPath (Join-Path $torchRoot "lib\asmjit.dll") `
        -DuplicatePath (Join-Path $torchRoot "bin\asmjit.dll")) {
        $removed += (Join-Path $torchRoot "bin\asmjit.dll")
    }

    foreach ($relativePath in @(
        "_inductor",
        "_dynamo",
        "onnx"
    )) {
        $fullPath = Join-Path $torchRoot $relativePath
        if (Remove-EngineRuntimePath -Path $fullPath) {
            $removed += $fullPath
        }
    }

    return $removed
}

function Remove-CTranslate2RuntimeSupportPayload {
    param([string]$InternalRoot)

    $removed = @()
    $ctranslateRoot = Join-Path $InternalRoot "ctranslate2"
    if (-not (Test-Path $ctranslateRoot)) {
        return $removed
    }

    foreach ($relativePath in @("converters", "specs")) {
        $fullPath = Join-Path $ctranslateRoot $relativePath
        if (Remove-EngineRuntimePath -Path $fullPath) {
            $removed += $fullPath
        }
    }

    return $removed
}

function Write-EngineSizeReport {
    param(
        [string]$RepoRoot,
        [string]$ArchivePath,
        [string]$InternalRoot,
        [datetime]$BuildStartedAtUtc
    )

    $reportRoot = Join-Path $RepoRoot ".cursor\debug\installer-size"
    $reportStamp = $BuildStartedAtUtc.ToString("yyyyMMdd-HHmmss")
    $reportDir = Join-Path $reportRoot $reportStamp
    New-Item -ItemType Directory -Force -Path $reportDir | Out-Null

    $topDirectories = @()
    if (Test-Path $InternalRoot) {
        $topDirectories = Get-ChildItem -Path $InternalRoot -Directory -ErrorAction SilentlyContinue |
            ForEach-Object {
                [PSCustomObject]@{
                    path = $_.FullName
                    size_bytes = (Get-DirectorySizeBytes -Path $_.FullName)
                }
            } |
            Sort-Object size_bytes -Descending |
            Select-Object -First 20
    }

    $topFiles = @()
    if (Test-Path $InternalRoot) {
        $topFiles = Get-ChildItem -Path $InternalRoot -Recurse -File -ErrorAction SilentlyContinue |
            Sort-Object Length -Descending |
            Select-Object -First 40 @{Name = "path"; Expression = { $_.FullName } }, @{Name = "size_bytes"; Expression = { [int64]$_.Length } }
    }

    $archiveItem = Get-Item -Path $ArchivePath
    $baseline = [ordered]@{
        engine_zip_mb = 709.68
        nsis_mb = 728.53
        msi_mb = 726.94
    }
    $summary = [ordered]@{
        generated_utc = $BuildStartedAtUtc.ToString("o")
        baseline_sizes_mb = $baseline
        engine_archive = [ordered]@{
            path = $archiveItem.FullName
            size_bytes = [int64]$archiveItem.Length
            size_mb = [math]::Round($archiveItem.Length / 1MB, 2)
        }
        top_internal_directories = @(
            $topDirectories | ForEach-Object {
                [ordered]@{
                    path = $_.path
                    size_bytes = $_.size_bytes
                    size_mb = [math]::Round($_.size_bytes / 1MB, 2)
                }
            }
        )
        top_internal_files = @(
            $topFiles | ForEach-Object {
                [ordered]@{
                    path = $_.path
                    size_bytes = $_.size_bytes
                    size_mb = [math]::Round($_.size_bytes / 1MB, 2)
                }
            }
        )
    }

    $jsonPath = Join-Path $reportDir "engine-size-report.json"
    $textPath = Join-Path $reportDir "engine-size-report.txt"
    $summary | ConvertTo-Json -Depth 6 | Set-Content -Path $jsonPath -Encoding utf8

    $textLines = @(
        "Generated UTC: $($summary.generated_utc)",
        "Baseline engine zip: $($baseline.engine_zip_mb) MB",
        "Baseline NSIS: $($baseline.nsis_mb) MB",
        "Baseline MSI: $($baseline.msi_mb) MB",
        "Engine archive: $($summary.engine_archive.path)",
        "Engine archive size: $($summary.engine_archive.size_bytes) bytes ($($summary.engine_archive.size_mb) MB)",
        "",
        "Top internal directories:"
    )
    $textLines += $summary.top_internal_directories | ForEach-Object {
        "  $($_.size_mb) MB`t$($_.path)"
    }
    $textLines += ""
    $textLines += "Top internal files:"
    $textLines += $summary.top_internal_files | ForEach-Object {
        "  $($_.size_mb) MB`t$($_.path)"
    }
    Set-Content -Path $textPath -Value $textLines -Encoding utf8

    return $reportDir
}

$repo = Split-Path $PSScriptRoot -Parent
Set-Location $repo
$buildStartedAtUtc = [datetime]::UtcNow

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

Write-Host "[INFO] Syncing pinned FFmpeg binaries..."
& (Join-Path $repo "scripts\download_ffmpeg.ps1")

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

$removedLibFiles = @(Remove-EngineRuntimeLibFiles -RootPath $internalRoot)
if ($removedLibFiles.Count -gt 0) {
    Write-Host "[INFO] Removed $($removedLibFiles.Count) packaged .lib files from engine runtime payload."
}
Assert-NoEngineRuntimeLibFiles -RootPath $internalRoot
Write-Host "[INFO] Verified packaged engine contains no .lib runtime files."

$removedPySide6Payload = @(Remove-OptionalPySide6Payload -InternalRoot $internalRoot)
if ($removedPySide6Payload.Count -gt 0) {
    Write-Host "[INFO] Removed $($removedPySide6Payload.Count) optional PySide6 runtime paths."
}

$removedPillowPayload = @(Remove-OptionalPillowRuntimePayload -InternalRoot $internalRoot)
if ($removedPillowPayload.Count -gt 0) {
    Write-Host "[INFO] Removed $($removedPillowPayload.Count) optional Pillow runtime paths."
}

$removedTorchPayload = @(Remove-OptionalTorchRuntimePayload -InternalRoot $internalRoot)
if ($removedTorchPayload.Count -gt 0) {
    Write-Host "[INFO] Removed $($removedTorchPayload.Count) optional torch runtime paths."
}

$removedCTranslate2Payload = @(Remove-CTranslate2RuntimeSupportPayload -InternalRoot $internalRoot)
if ($removedCTranslate2Payload.Count -gt 0) {
    Write-Host "[INFO] Removed $($removedCTranslate2Payload.Count) optional ctranslate2 support paths."
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

$sizeReportDir = Write-EngineSizeReport `
    -RepoRoot $repo `
    -ArchivePath $engineArchivePath `
    -InternalRoot $internalRoot `
    -BuildStartedAtUtc $buildStartedAtUtc
Write-Host "[INFO] Engine size report: $sizeReportDir"

Write-Host "[OK] Engine build complete."
Write-Host "[OK] Engine archive: $engineArchivePath"
