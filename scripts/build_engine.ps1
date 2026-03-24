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

function Remove-PathWithRetries {
    param(
        [string]$Path,
        [int]$Attempts = 8,
        [int]$DelayMilliseconds = 750
    )

    if (-not (Test-Path $Path)) {
        return $false
    }

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            Remove-Item -Recurse -Force $Path
            return $true
        }
        catch {
            if ($attempt -eq $Attempts) {
                throw
            }
            Start-Sleep -Milliseconds $DelayMilliseconds
        }
    }

    return $false
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

function New-ZipFromFileEntries {
    param(
        [string]$ZipPath,
        [System.Collections.Generic.List[hashtable]]$Entries
    )

    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    if (Test-Path $ZipPath) {
        Remove-PathWithRetries -Path $ZipPath | Out-Null
    }
    $zip = [System.IO.Compression.ZipFile]::Open(
        $ZipPath,
        [System.IO.Compression.ZipArchiveMode]::Create
    )
    try {
        foreach ($entry in $Entries) {
            $fullPath = [string]$entry.FullPath
            $entryName = ([string]$entry.EntryName) -replace '\\', '/'
            if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
                continue
            }
            $null = [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $zip,
                $fullPath,
                $entryName,
                [System.IO.Compression.CompressionLevel]::Optimal
            )
        }
    }
    finally {
        $zip.Dispose()
    }
}

function Publish-FileWithReplaceRetries {
    param(
        [string]$SourcePath,
        [string]$DestinationPath,
        [int]$Attempts = 8,
        [int]$DelayMilliseconds = 750
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            if (Test-Path $DestinationPath) {
                Remove-PathWithRetries -Path $DestinationPath -Attempts 1 | Out-Null
            }
            Move-Item -Force -Path $SourcePath -Destination $DestinationPath
            return
        }
        catch {
            if ($attempt -eq $Attempts) {
                throw
            }
            Start-Sleep -Milliseconds $DelayMilliseconds
        }
    }
}

function Test-InternalPathIsTorchOrPySide6 {
    param([string]$RelativePath)

    $normalized = ($RelativePath -replace '/', '\').TrimStart('\')
    if ($normalized -like 'torch\*' -or $normalized -eq 'torch') {
        return $true
    }
    if ($normalized -like 'PySide6\*' -or $normalized -eq 'PySide6') {
        return $true
    }
    return $false
}

function Write-EngineSizeReport {
    param(
        [string]$RepoRoot,
        [string[]]$ArchivePaths,
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

    $archiveRows = @()
    $totalBytes = [int64]0
    foreach ($p in $ArchivePaths) {
        if (-not (Test-Path -LiteralPath $p)) {
            continue
        }
        $item = Get-Item -LiteralPath $p
        $totalBytes += [int64]$item.Length
        $archiveRows += [ordered]@{
            path = $item.FullName
            size_bytes = [int64]$item.Length
            size_mb = [math]::Round($item.Length / 1MB, 2)
        }
    }
    $baseline = [ordered]@{
        engine_zip_mb = 709.68
        nsis_mb = 728.53
        msi_mb = 726.94
    }
    $summary = [ordered]@{
        generated_utc = $BuildStartedAtUtc.ToString("o")
        baseline_sizes_mb = $baseline
        engine_archives_total_bytes = $totalBytes
        engine_archives_total_mb = [math]::Round($totalBytes / 1MB, 2)
        engine_archives = @($archiveRows)
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
        "Engine archives total: $($summary.engine_archives_total_bytes) bytes ($($summary.engine_archives_total_mb) MB)",
        ""
    )
    foreach ($row in $summary.engine_archives) {
        $textLines += "  Part: $($row.path)"
        $textLines += "    $($row.size_bytes) bytes ($($row.size_mb) MB)"
    }
    $textLines += ""
    $textLines += @(
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

$supportedMinPython = [version]"3.11"
$supportedMaxPythonExclusive = [version]"3.13"

$venvDir = Join-Path $repo ".venv"
$venvConfig = Join-Path $venvDir "pyvenv.cfg"
$venvPython = Join-Path $repo ".venv\Scripts\python.exe"
if ((Test-Path $venvConfig) -and (Test-Path $venvPython)) {
    $venvConfigValues = @{}
    foreach ($line in Get-Content -Path $venvConfig -ErrorAction SilentlyContinue) {
        if ($line -match "^\s*([^=]+?)\s*=\s*(.+?)\s*$") {
            $venvConfigValues[$matches[1].Trim()] = $matches[2].Trim()
        }
    }

    $basePython = $null
    if ($venvConfigValues.ContainsKey("executable")) {
        $basePython = $venvConfigValues["executable"]
    }
    elseif ($venvConfigValues.ContainsKey("home")) {
        $basePython = Join-Path $venvConfigValues["home"] "python.exe"
    }

    if ($basePython -and -not (Test-Path $basePython)) {
        Write-Host "[INFO] Existing virtual environment points to missing Python: $basePython"
        Write-Host "[INFO] Recreating virtual environment..."
        Remove-PathWithRetries -Path $venvDir | Out-Null
    }
}

if (-not (Test-Path $venvPython)) {
    Write-Host "[INFO] Creating virtual environment..."
    & py -3 -m venv ".venv"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create virtual environment."
    }
}

if (-not (Test-Path $venvPython)) {
    throw "Virtual environment python not found at $venvPython"
}

$pythonVersionText = (& $venvPython -c "import sys; print('.'.join(str(part) for part in sys.version_info[:3]))").Trim()
if (-not $pythonVersionText) {
    throw "Failed to detect virtual environment Python version."
}

$pythonVersion = [version]$pythonVersionText
if ($pythonVersion -lt $supportedMinPython -or $pythonVersion -ge $supportedMaxPythonExclusive) {
    throw "Cue packaging currently supports Python $supportedMinPython through 3.12.x. Found $pythonVersion at $venvPython. Install Python 3.12, then recreate C:\Cue_repo\.venv or rerun this script so it can recreate the environment automatically."
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

& $venvPython -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('PyInstaller') else 1)"
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
$pyInstallerRunRoot = Join-Path $repo (".cursor\debug\pyinstaller\" + $buildStartedAtUtc.ToString("yyyyMMdd-HHmmss"))
$engineBuildRoot = Join-Path $pyInstallerRunRoot "build"
$engineDistRoot = Join-Path $pyInstallerRunRoot "dist"
$engineBuildDir = Join-Path $engineBuildRoot "CueEngine"
$engineDistDir = Join-Path $engineDistRoot "CueEngine"
$engineTemplate = Join-Path $repo "tools\pyinstaller.engine.spec.in"
$engineArchiveDirectory = Join-Path $repo "desktop\src-tauri"
$enginePartDefinitions = @(
    @{ Name = "cue-engine-01-executables.zip"; Label = "Unpacking core engine programs..." }
    @{ Name = "cue-engine-02-torch.zip"; Label = "Unpacking speech libraries..." }
    @{ Name = "cue-engine-03-pyside6.zip"; Label = "Unpacking display libraries..." }
    @{ Name = "cue-engine-04-internal.zip"; Label = "Unpacking remaining engine files..." }
)
$engineManifestName = "cue-engine-parts.json"

if (Test-Path $engineSpec) {
    Remove-Item -Force $engineSpec
}
New-Item -ItemType Directory -Force -Path $engineBuildRoot | Out-Null
New-Item -ItemType Directory -Force -Path $engineDistRoot | Out-Null

Copy-Item -Force $engineTemplate $engineSpec

Write-Host "[INFO] Running PyInstaller for engine..."
Write-Host "[INFO] PyInstaller temp output root: $pyInstallerRunRoot"
& $venvPython -m PyInstaller --noconfirm --workpath $engineBuildRoot --distpath $engineDistRoot $engineSpec
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

$legacySingleZip = Join-Path $engineArchiveDirectory "cue-local-engine.zip"
$manifestPath = Join-Path $engineArchiveDirectory $engineManifestName
$tempPublishRoot = Join-Path $repo (".cursor\debug\engine-publish\" + $buildStartedAtUtc.ToString("yyyyMMdd-HHmmss"))
New-Item -ItemType Directory -Force -Path $tempPublishRoot | Out-Null

# Part 1: root executables and any non-_internal files
$part1Entries = New-Object System.Collections.Generic.List[hashtable]
Get-ChildItem -Path $engineDistDir -Force | Where-Object { $_.Name -ne "_internal" } | ForEach-Object {
    if ($_.PSIsContainer) {
        Get-ChildItem -Path $_.FullName -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
            $rel = $_.FullName.Substring($engineDistDir.Length).TrimStart('\', '/')
            $part1Entries.Add(@{ FullPath = $_.FullName; EntryName = ($rel -replace '\\', '/') })
        }
    }
    else {
        $part1Entries.Add(@{ FullPath = $_.FullName; EntryName = $_.Name })
    }
}
$zip1Temp = Join-Path $tempPublishRoot $enginePartDefinitions[0].Name
$zip1 = Join-Path $engineArchiveDirectory $enginePartDefinitions[0].Name
Write-Host "[INFO] Creating $($enginePartDefinitions[0].Name) ($($part1Entries.Count) entries)"
New-ZipFromFileEntries -ZipPath $zip1Temp -Entries $part1Entries

# Part 2: _internal/torch
$torchRoot = Join-Path $internalRoot "torch"
$part2Entries = New-Object System.Collections.Generic.List[hashtable]
if (Test-Path $torchRoot) {
    Get-ChildItem -Path $torchRoot -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
        $rel = $_.FullName.Substring($internalRoot.Length).TrimStart('\', '/')
        $part2Entries.Add(@{ FullPath = $_.FullName; EntryName = "_internal/" + ($rel -replace '\\', '/') })
    }
}
$zip2Temp = Join-Path $tempPublishRoot $enginePartDefinitions[1].Name
$zip2 = Join-Path $engineArchiveDirectory $enginePartDefinitions[1].Name
Write-Host "[INFO] Creating $($enginePartDefinitions[1].Name) ($($part2Entries.Count) entries)"
New-ZipFromFileEntries -ZipPath $zip2Temp -Entries $part2Entries

# Part 3: _internal/PySide6
$pysideRoot = Join-Path $internalRoot "PySide6"
$part3Entries = New-Object System.Collections.Generic.List[hashtable]
if (Test-Path $pysideRoot) {
    Get-ChildItem -Path $pysideRoot -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
        $rel = $_.FullName.Substring($internalRoot.Length).TrimStart('\', '/')
        $part3Entries.Add(@{ FullPath = $_.FullName; EntryName = "_internal/" + ($rel -replace '\\', '/') })
    }
}
$zip3Temp = Join-Path $tempPublishRoot $enginePartDefinitions[2].Name
$zip3 = Join-Path $engineArchiveDirectory $enginePartDefinitions[2].Name
Write-Host "[INFO] Creating $($enginePartDefinitions[2].Name) ($($part3Entries.Count) entries)"
New-ZipFromFileEntries -ZipPath $zip3Temp -Entries $part3Entries

# Part 4: _internal remainder (not torch, not PySide6)
$part4Entries = New-Object System.Collections.Generic.List[hashtable]
Get-ChildItem -Path $internalRoot -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
    $rel = $_.FullName.Substring($internalRoot.Length).TrimStart('\', '/')
    if (-not (Test-InternalPathIsTorchOrPySide6 -RelativePath $rel)) {
        $part4Entries.Add(@{ FullPath = $_.FullName; EntryName = "_internal/" + ($rel -replace '\\', '/') })
    }
}
$zip4Temp = Join-Path $tempPublishRoot $enginePartDefinitions[3].Name
$zip4 = Join-Path $engineArchiveDirectory $enginePartDefinitions[3].Name
Write-Host "[INFO] Creating $($enginePartDefinitions[3].Name) ($($part4Entries.Count) entries)"
New-ZipFromFileEntries -ZipPath $zip4Temp -Entries $part4Entries

$manifestParts = @()
for ($i = 0; $i -lt $enginePartDefinitions.Count; $i++) {
    $manifestParts += [ordered]@{
        file = $enginePartDefinitions[$i].Name
        label = $enginePartDefinitions[$i].Label
    }
}
$manifestObj = [ordered]@{
    version = 1
    parts = $manifestParts
}
$manifestJson = $manifestObj | ConvertTo-Json -Depth 5
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText((Join-Path $tempPublishRoot $engineManifestName), $manifestJson, $utf8NoBom)

if (Test-Path $legacySingleZip) {
    Remove-PathWithRetries -Path $legacySingleZip | Out-Null
}
Publish-FileWithReplaceRetries -SourcePath $zip1Temp -DestinationPath $zip1
Publish-FileWithReplaceRetries -SourcePath $zip2Temp -DestinationPath $zip2
Publish-FileWithReplaceRetries -SourcePath $zip3Temp -DestinationPath $zip3
Publish-FileWithReplaceRetries -SourcePath $zip4Temp -DestinationPath $zip4
Publish-FileWithReplaceRetries -SourcePath (Join-Path $tempPublishRoot $engineManifestName) -DestinationPath $manifestPath
Write-Host "[INFO] Wrote manifest $manifestPath"

$allZipPaths = @($zip1, $zip2, $zip3, $zip4)
foreach ($zp in $allZipPaths) {
    if (-not (Test-Path $zp)) {
        throw "Engine part zip was not created: $zp"
    }
    $sz = (Get-Item $zp).Length
    Write-Host ("[INFO] {0}: {1:N0} bytes ({2:N2} MB)" -f (Split-Path $zp -Leaf), $sz, ($sz / 1MB))
}

$sizeReportDir = Write-EngineSizeReport `
    -RepoRoot $repo `
    -ArchivePaths $allZipPaths `
    -InternalRoot $internalRoot `
    -BuildStartedAtUtc $buildStartedAtUtc
Write-Host "[INFO] Engine size report: $sizeReportDir"

Write-Host "[OK] Engine build complete."
Write-Host "[OK] Engine parts and manifest under $engineArchiveDirectory"
