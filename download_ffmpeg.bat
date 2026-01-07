@echo off
setlocal enabledelayedexpansion

set "URL=https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
set "OUTDIR=%CD%\bin"
set "TEMP_DIR=%CD%\_ffmpeg_tmp"

if not exist "%OUTDIR%" mkdir "%OUTDIR%"
if exist "%TEMP_DIR%" rmdir /S /Q "%TEMP_DIR%"
mkdir "%TEMP_DIR%"

powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri '%URL%' -OutFile '%TEMP_DIR%\ffmpeg.zip'"
if %ERRORLEVEL% NEQ 0 (
  echo [ERROR] Download failed.
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path '%TEMP_DIR%\ffmpeg.zip' -DestinationPath '%TEMP_DIR%\extract' -Force"
if %ERRORLEVEL% NEQ 0 (
  echo [ERROR] Extraction failed.
  exit /b 1
)

set "FFMPEG_EXE="
set "FFPROBE_EXE="
for /f "delims=" %%F in ('dir /b /s "%TEMP_DIR%\extract\ffmpeg.exe"') do if not defined FFMPEG_EXE set "FFMPEG_EXE=%%F"
for /f "delims=" %%F in ('dir /b /s "%TEMP_DIR%\extract\ffprobe.exe"') do if not defined FFPROBE_EXE set "FFPROBE_EXE=%%F"

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

echo FFmpeg binaries placed in:
echo %OUTDIR%\ffmpeg.exe
echo %OUTDIR%\ffprobe.exe
echo [SUCCESS] FFmpeg download complete.
