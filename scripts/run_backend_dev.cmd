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

rem Write the port without trailing spaces/newlines (some consumers are picky).
(echo|set /p="%BACKEND_PORT%") > "%PORT_FILE%"

echo Starting backend server on http://127.0.0.1:%BACKEND_PORT%/health
echo Example events URL: http://127.0.0.1:%BACKEND_PORT%/jobs/{job_id}/events
echo Logs: %LOG_FILE%
echo Port file: %PORT_FILE%

set "CUE_BACKEND_PORT=%BACKEND_PORT%"

rem If a backend is already running, don't start a second one (avoids log-file locks).
powershell -NoProfile -Command "try { $r=Invoke-WebRequest -UseBasicParsing http://127.0.0.1:%BACKEND_PORT%/health -TimeoutSec 1; if($r.StatusCode -eq 200){ exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>nul
if %errorlevel%==0 (
  echo Backend already healthy on port %BACKEND_PORT%. Not starting another instance.
  exit /b 0
)

python -m app.backend_server > "%LOG_FILE%" 2>&1
