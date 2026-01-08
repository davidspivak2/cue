@echo off
setlocal

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0download_ffmpeg.ps1"
if %ERRORLEVEL% NEQ 0 (
  echo [ERROR] FFmpeg download failed.
  exit /b 1
)
