$ErrorActionPreference = "Stop"

$defaultVersion = "8.0.1"
$defaultFlavor = "essentials_build"
$defaultUrl = "https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-8.0.1-essentials_build.zip"
$defaultSha256 = "e2aaeaa0fdbc397d4794828086424d4aaa2102cef1fb6874f6ffd29c0b88b673"

$requestedUrl = if ([string]::IsNullOrWhiteSpace($env:CUE_FFMPEG_URL)) {
    $defaultUrl
} else {
    $env:CUE_FFMPEG_URL.Trim()
}
$isDefaultPackage = $requestedUrl -eq $defaultUrl
$expectedVersion = if ($isDefaultPackage) { $defaultVersion } else { $null }
$expectedFlavor = if ($isDefaultPackage) { $defaultFlavor } else { $null }
$expectedSha256 = if ($isDefaultPackage) { $defaultSha256 } else { $null }

$root = Split-Path $PSScriptRoot -Parent
$outDir = Join-Path $root "bin"
$tempDir = Join-Path $root "_ffmpeg_tmp"
$zipPath = Join-Path $tempDir "ffmpeg.zip"
$extractDir = Join-Path $tempDir "extract"
$metadataPath = Join-Path $outDir "ffmpeg-source.json"
$ffmpegTarget = Join-Path $outDir "ffmpeg.exe"
$ffprobeTarget = Join-Path $outDir "ffprobe.exe"

function Get-VersionBanner([string]$exePath) {
    if (-not (Test-Path $exePath)) {
        return $null
    }
    try {
        return (& $exePath -version 2>$null | Select-Object -First 1)
    } catch {
        return $null
    }
}

function Test-ExistingBundleMatchesRequest {
    param(
        [string]$MetadataPath,
        [string]$RequestedUrl,
        [string]$FfmpegPath,
        [string]$FfprobePath,
        [string]$ExpectedVersion,
        [string]$ExpectedFlavor
    )

    if (-not (Test-Path $MetadataPath) -or -not (Test-Path $FfmpegPath) -or -not (Test-Path $FfprobePath)) {
        return $false
    }

    try {
        $metadata = Get-Content $MetadataPath -Raw | ConvertFrom-Json
    } catch {
        return $false
    }

    if ($metadata.url -ne $RequestedUrl) {
        return $false
    }

    $ffmpegBanner = Get-VersionBanner $FfmpegPath
    $ffprobeBanner = Get-VersionBanner $FfprobePath
    if (-not $ffmpegBanner -or -not $ffprobeBanner) {
        return $false
    }

    if ($ExpectedVersion -and $ExpectedFlavor) {
        $expectedFfmpegPrefix = "ffmpeg version $ExpectedVersion-$ExpectedFlavor"
        $expectedFfprobePrefix = "ffprobe version $ExpectedVersion-$ExpectedFlavor"
        return $ffmpegBanner.StartsWith($expectedFfmpegPrefix) -and $ffprobeBanner.StartsWith($expectedFfprobePrefix)
    }

    return $true
}

if (-not (Test-Path $outDir)) {
    New-Item -ItemType Directory -Path $outDir | Out-Null
}

if (Test-ExistingBundleMatchesRequest `
    -MetadataPath $metadataPath `
    -RequestedUrl $requestedUrl `
    -FfmpegPath $ffmpegTarget `
    -FfprobePath $ffprobeTarget `
    -ExpectedVersion $expectedVersion `
    -ExpectedFlavor $expectedFlavor) {
    Write-Host "[INFO] FFmpeg binaries already match the requested package."
    Write-Host "[INFO] Source: $requestedUrl"
    Write-Host $ffmpegTarget
    Write-Host $ffprobeTarget
    return
}

if (Test-Path $tempDir) {
    Remove-Item -Recurse -Force $tempDir
}
New-Item -ItemType Directory -Path $tempDir | Out-Null

Write-Host "[INFO] Downloading FFmpeg package from $requestedUrl"
Invoke-WebRequest -Uri $requestedUrl -OutFile $zipPath

if ($expectedSha256) {
    $archiveHash = (Get-FileHash -Path $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($archiveHash -ne $expectedSha256) {
        throw "Downloaded FFmpeg archive hash mismatch. Expected $expectedSha256 but got $archiveHash."
    }
}

Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force

$ffmpegExe = Get-ChildItem -Path $extractDir -Filter "ffmpeg.exe" -Recurse | Select-Object -First 1
$ffprobeExe = Get-ChildItem -Path $extractDir -Filter "ffprobe.exe" -Recurse | Select-Object -First 1

if (-not $ffmpegExe) {
    throw "ffmpeg.exe not found after extraction."
}
if (-not $ffprobeExe) {
    throw "ffprobe.exe not found after extraction."
}

if ($expectedVersion -and $expectedFlavor) {
    $ffmpegBanner = Get-VersionBanner $ffmpegExe.FullName
    $ffprobeBanner = Get-VersionBanner $ffprobeExe.FullName
    $expectedFfmpegPrefix = "ffmpeg version $expectedVersion-$expectedFlavor"
    $expectedFfprobePrefix = "ffprobe version $expectedVersion-$expectedFlavor"
    if (-not $ffmpegBanner.StartsWith($expectedFfmpegPrefix)) {
        throw "Downloaded ffmpeg.exe did not match the pinned build. Saw: $ffmpegBanner"
    }
    if (-not $ffprobeBanner.StartsWith($expectedFfprobePrefix)) {
        throw "Downloaded ffprobe.exe did not match the pinned build. Saw: $ffprobeBanner"
    }
}

Copy-Item -Path $ffmpegExe.FullName -Destination $ffmpegTarget -Force
Copy-Item -Path $ffprobeExe.FullName -Destination $ffprobeTarget -Force

@{
    url = $requestedUrl
    version = $expectedVersion
    flavor = $expectedFlavor
    archive_sha256 = $expectedSha256
} | ConvertTo-Json | Set-Content -Path $metadataPath -Encoding UTF8

Remove-Item -Recurse -Force $tempDir

Write-Host "FFmpeg binaries placed in:"
Write-Host $ffmpegTarget
Write-Host $ffprobeTarget
Write-Host "[SUCCESS] FFmpeg download complete."
