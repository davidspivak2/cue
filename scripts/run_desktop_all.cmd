@echo off
setlocal enabledelayedexpansion

rem Runs: backend deps check/install -> desktop deps check/install -> start backend -> wait for /health -> start desktop dev

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
echo === Starting backend in a new window ===
if not exist "%REPO%\scripts\run_backend_dev.cmd" (
  echo ERROR: %REPO%\scripts\run_backend_dev.cmd not found.
  exit /b 1
)

start "Cue Backend" cmd /k ""%REPO%\scripts\run_backend_dev.cmd""

echo Waiting for backend /health...
rem Try up to 30 seconds total (30 attempts x 1s)
set "OK="
for /l %%A in (1,1,30) do (
  rem Refresh port if backend wrote backend_port.txt
  if exist "%PORT_FILE%" set /p PORT=<"%PORT_FILE%"

  curl -s "http://127.0.0.1:!PORT!/health" | findstr /c:"""ok"":true" >nul
  if not errorlevel 1 (
    set "OK=1"
    goto :health_ok
  )
  timeout /t 1 /nobreak >nul
)

:health_ok
if not defined OK (
  echo ERROR: backend did not become healthy at http://127.0.0.1:!PORT!/health
  echo Check the backend window and %EXTRA%\backend_dev.log
  exit /b 1
)

echo Backend healthy on port !PORT!.
echo.
echo === Launching desktop (Tauri) ===
if not exist "%REPO%\scripts\run_desktop_dev.cmd" (
  echo ERROR: %REPO%\scripts\run_desktop_dev.cmd not found.
  exit /b 1
)

call "%REPO%\scripts\run_desktop_dev.cmd"
exit /b %errorlevel%