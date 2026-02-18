$ErrorActionPreference = "Stop"

$url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
$root = Split-Path $PSScriptRoot -Parent
$outDir = Join-Path $root "bin"
$tempDir = Join-Path $root "_ffmpeg_tmp"
$zipPath = Join-Path $tempDir "ffmpeg.zip"
$extractDir = Join-Path $tempDir "extract"

if (-not (Test-Path $outDir)) {
    New-Item -ItemType Directory -Path $outDir | Out-Null
}
if (Test-Path $tempDir) {
    Remove-Item -Recurse -Force $tempDir
}
New-Item -ItemType Directory -Path $tempDir | Out-Null

Invoke-WebRequest -Uri $url -OutFile $zipPath
Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force

$ffmpegExe = Get-ChildItem -Path $extractDir -Filter "ffmpeg.exe" -Recurse | Select-Object -First 1
$ffprobeExe = Get-ChildItem -Path $extractDir -Filter "ffprobe.exe" -Recurse | Select-Object -First 1

if (-not $ffmpegExe) {
    throw "ffmpeg.exe not found after extraction."
}
if (-not $ffprobeExe) {
    throw "ffprobe.exe not found after extraction."
}

Copy-Item -Path $ffmpegExe.FullName -Destination (Join-Path $outDir "ffmpeg.exe") -Force
Copy-Item -Path $ffprobeExe.FullName -Destination (Join-Path $outDir "ffprobe.exe") -Force

Remove-Item -Recurse -Force $tempDir

Write-Host "FFmpeg binaries placed in:"
Write-Host (Join-Path $outDir "ffmpeg.exe")
Write-Host (Join-Path $outDir "ffprobe.exe")
Write-Host "[SUCCESS] FFmpeg download complete."
