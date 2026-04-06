@echo off
setlocal

rem If backend_port.txt exists, use it. Otherwise default to 8765.
set "PORT_FILE=C:\Cue_extra\backend_port.txt"
set "CUE_BACKEND_PORT=8765"
if exist "%PORT_FILE%" (
  rem Read first token to avoid trailing/leading whitespace (e.g. "8765 ").
  for /f "usebackq tokens=1" %%P in ("%PORT_FILE%") do set "CUE_BACKEND_PORT=%%P"
)

echo Using backend port: %CUE_BACKEND_PORT%

cd /d C:\Cue_repo\desktop

rem Tauri dev expects Vite to be on 5173 (strictPort=true).
set "VITE_PORT=5173"

if exist "%USERPROFILE%\.cargo\bin\cargo.exe" (
  set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
)

where cargo >nul 2>nul
if not %errorlevel%==0 (
  echo ERROR: Rust's cargo tool was not found in PATH.
  echo The desktop app uses Tauri, and Tauri needs the Rust toolchain to start.
  echo.
  echo Install Rust from https://rustup.rs/ and then close this window.
  echo After the install finishes, open a new PowerShell or Command Prompt window and run the app again.
  exit /b 1
)

rem Check both IPv4 and IPv6 for port availability; auto-cleanup stale Cue Vite if found.
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Cue_repo\scripts\ensure_vite_port.ps1" -VitePort %VITE_PORT%
if not %errorlevel%==0 (
  echo ERROR: Port %VITE_PORT% is already in use.
  echo Close the existing Vite/Tauri dev session that is using %VITE_PORT%.
  exit /b 1
)

rem Prefer exact scripts if present. Do NOT guess silently.
node -e "const s=require('./package.json').scripts||{}; process.exit(s['tauri:dev']?0:1)"
if %errorlevel%==0 (
  echo Running: npm run tauri:dev
  npm run tauri:dev
  exit /b %errorlevel%
)

node -e "const s=require('./package.json').scripts||{}; process.exit(s['tauri']?0:1)"
if %errorlevel%==0 (
  echo Running: npm run tauri -- dev
  npm run tauri -- dev
  exit /b %errorlevel%
)

node -e "const s=require('./package.json').scripts||{}; process.exit(s['dev']?0:1)"
if %errorlevel%==0 (
  echo Running: npm run dev
  npm run dev
  exit /b %errorlevel%
)

node -e "const s=require('./package.json').scripts||{}; process.exit(s['start']?0:1)"
if %errorlevel%==0 (
  echo Running: npm run start
  npm run start
  exit /b %errorlevel%
)

echo ERROR: Could not find a known dev script in desktop\package.json.
echo Available scripts:
npm run
exit /b 1
