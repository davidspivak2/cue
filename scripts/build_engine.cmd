@echo off
setlocal

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_engine.ps1"
exit /b %errorlevel%
