@echo off
rem PR2 dev runner for the backend stub.
rem Logs overwrite each run for simplicity.

set "LOG_DIR=C:\Cue_extra"
set "LOG_FILE=%LOG_DIR%\backend_dev.log"
set "PORT_FILE=%LOG_DIR%\backend_port.txt"
set "BACKEND_PORT=8765"

if not exist "%LOG_DIR%" (
  mkdir "%LOG_DIR%"
)

echo %BACKEND_PORT% > "%PORT_FILE%"

echo Starting backend server on http://127.0.0.1:%BACKEND_PORT%/health
echo Example events URL: http://127.0.0.1:%BACKEND_PORT%/jobs/{job_id}/events
echo Logs: %LOG_FILE%
echo Port file: %PORT_FILE%

set "CUE_BACKEND_PORT=%BACKEND_PORT%"

python -m app.backend_server > "%LOG_FILE%" 2>&1
