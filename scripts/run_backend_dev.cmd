@echo off
rem PR2 dev runner for the backend stub.
rem Logs overwrite each run for simplicity.

set "LOG_DIR=C:\Cue_extra"
set "LOG_FILE=%LOG_DIR%\backend_dev.log"

if not exist "%LOG_DIR%" (
  mkdir "%LOG_DIR%"
)

echo Starting backend server on http://127.0.0.1:8765/health

python -m app.backend_server > "%LOG_FILE%" 2>&1
