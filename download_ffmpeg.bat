@echo off
setlocal enabledelayedexpansion

set "URL=https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-full.7z"
set "OUTDIR=%CD%\bin"
set "TEMP_DIR=%CD%\_ffmpeg_tmp"

if not exist "%OUTDIR%" mkdir "%OUTDIR%"
if not exist "%TEMP_DIR%" mkdir "%TEMP_DIR%"

powershell -Command "Invoke-WebRequest -Uri '%URL%' -OutFile '%TEMP_DIR%\ffmpeg.7z'"
if %ERRORLEVEL% NEQ 0 (
  echo [ERROR] Download failed.
  exit /b 1
)

powershell -Command "& {\
  $zip='%TEMP_DIR%\ffmpeg.7z';\
  $dest='%TEMP_DIR%\extract';\
  if (!(Test-Path $dest)) { New-Item -ItemType Directory -Path $dest | Out-Null };\
  & 7z x $zip -o$dest | Out-Null;\
}"
if %ERRORLEVEL% NEQ 0 (
  echo [ERROR] Extraction failed. Ensure 7-Zip is installed and in PATH.
  exit /b 1
)

for /f "delims=" %%F in ('dir /b /s "%TEMP_DIR%\extract\ffmpeg.exe"') do set "FFMPEG_EXE=%%F"
for /f "delims=" %%F in ('dir /b /s "%TEMP_DIR%\extract\ffprobe.exe"') do set "FFPROBE_EXE=%%F"

if not defined FFMPEG_EXE (
  echo [ERROR] ffmpeg.exe not found after extraction.
  exit /b 1
)
if not defined FFPROBE_EXE (
  echo [ERROR] ffprobe.exe not found after extraction.
  exit /b 1
)

copy /Y "%FFMPEG_EXE%" "%OUTDIR%\ffmpeg.exe" >nul
copy /Y "%FFPROBE_EXE%" "%OUTDIR%\ffprobe.exe" >nul

rmdir /S /Q "%TEMP_DIR%"

echo FFmpeg binaries placed in %OUTDIR%
