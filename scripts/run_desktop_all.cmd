@echo off
setlocal enabledelayedexpansion

rem Runs: backend deps check/install -> desktop deps check/install -> start backend -> wait for /health -> start desktop dev
rem Fixes a common failure where backend_port.txt contains trailing spaces, producing a URL like "http://127.0.0.1:8765 /health".

set "REPO=C:\Cue_repo"
set "EXTRA=C:\Cue_extra"
set "PORT_FILE=%EXTRA%\backend_port.txt"
set "PORT=8765"

if not exist "%EXTRA%" mkdir "%EXTRA%"

cd /d "%REPO%"

echo === Checking Python backend deps (FastAPI/Uvicorn/Pydantic) ===
python -c "import fastapi, uvicorn, pydantic" >nul 2>nul
if errorlevel 1 (
  echo Backend deps missing. Running scripts\install_backend_dev_deps.cmd ...
  if not exist "%REPO%\scripts\install_backend_dev_deps.cmd" (
    echo ERROR: %REPO%\scripts\install_backend_dev_deps.cmd not found.
    exit /b 1
  )
  call "%REPO%\scripts\install_backend_dev_deps.cmd"
  if errorlevel 1 (
    echo ERROR: backend deps install failed.
    exit /b 1
  )
) else (
  echo Backend deps OK.
)

echo.
echo === Checking desktop deps (node_modules) ===
if not exist "%REPO%\desktop\node_modules" (
  echo Desktop deps missing. Running scripts\install_desktop_dev_deps.cmd ...
  if not exist "%REPO%\scripts\install_desktop_dev_deps.cmd" (
    echo ERROR: %REPO%\scripts\install_desktop_dev_deps.cmd not found.
    exit /b 1
  )
  call "%REPO%\scripts\install_desktop_dev_deps.cmd"
  if errorlevel 1 (
    echo ERROR: desktop deps install failed.
    exit /b 1
  )
) else (
  echo Desktop deps OK.
)

echo.
echo === Checking if backend is already healthy ===
call :read_port
call :probe_health
if "!HEALTH_HTTP!"=="200" (
  echo Backend already running. Stopping it so a fresh backend window can open...
  powershell -NoProfile -Command "if (Test-Path '%EXTRA%\backend_pid.json') { $j = Get-Content '%EXTRA%\backend_pid.json' -Raw | ConvertFrom-Json; if ($j.pid) { Start-Process -FilePath taskkill -ArgumentList '/PID',$j.pid,'/T','/F' -Wait -WindowStyle Hidden } }"
  timeout /t 2 /nobreak >nul
)

echo.
echo === Starting backend in a new window ===
if not exist "%REPO%\scripts\run_backend_dev.cmd" (
  echo ERROR: %REPO%\scripts\run_backend_dev.cmd not found.
  exit /b 1
)

start "Cue Backend" powershell -NoProfile -ExecutionPolicy Bypass -File "%REPO%\scripts\run_backend_dev.ps1"

echo Waiting for backend /health...
set /a HEALTH_TRIES=60

:wait_loop
call :read_port
call :probe_health
if "!HEALTH_HTTP!"=="200" goto :health_ok

set /a HEALTH_TRIES-=1
if !HEALTH_TRIES! LEQ 0 goto :health_fail

timeout /t 1 /nobreak >nul
goto :wait_loop

:health_ok
echo Backend is healthy at !HEALTH_URL!
goto :launch_desktop

:health_fail
echo ERROR: backend did not become healthy.
echo   Last port read : "!PORT!"
echo   Last health URL : !HEALTH_URL!
echo   Last HTTP code  : !HEALTH_HTTP!
echo Check the backend window and %EXTRA%\backend_dev.log
exit /b 1

:launch_desktop
echo.
echo === Launching desktop (Tauri) ===
if not exist "%REPO%\scripts\run_desktop_dev.cmd" (
  echo ERROR: %REPO%\scripts\run_desktop_dev.cmd not found.
  set "EXIT_CODE=1"
  goto :cleanup
)

call "%REPO%\scripts\run_desktop_dev.cmd"
set "EXIT_CODE=%errorlevel%"
goto :cleanup

:cleanup
rem When desktop exits (app closed or Ctrl+C), shut down the backend so nothing is left running.
if exist "%PORT_FILE%" (
  echo.
  echo === Shutting down backend ===
  powershell -NoProfile -Command "if (Test-Path '%EXTRA%\backend_pid.json') { $j = Get-Content '%EXTRA%\backend_pid.json' -Raw | ConvertFrom-Json; if ($j.pid) { Start-Process -FilePath taskkill -ArgumentList '/PID',$j.pid,'/T','/F' -Wait -WindowStyle Hidden; Write-Host 'Backend stopped.' } }"
)
exit /b %EXIT_CODE%

rem --- helpers ---

:read_port
rem Read first token from backend_port.txt to avoid trailing/leading spaces.
if exist "%PORT_FILE%" (
  for /f "usebackq tokens=1" %%P in ("%PORT_FILE%") do set "PORT=%%P"
)
exit /b 0

:probe_health
set "HEALTH_URL=http://127.0.0.1:!PORT!/health"
set "HEALTH_HTTP="
for /f %%H in ('curl.exe --silent --output nul --write-out "%%{http_code}" "!HEALTH_URL!" 2^>nul') do set "HEALTH_HTTP=%%H"
if not defined HEALTH_HTTP set "HEALTH_HTTP=000"
exit /b 0