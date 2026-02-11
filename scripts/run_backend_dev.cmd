@echo off
rem Backend dev runner. Delegates to PowerShell for clean Ctrl+C handling
rem (no "Terminate batch job" prompt, closes window, kills Cue UI on exit).

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_backend_dev.ps1"
exit /b %errorlevel%
