@echo off
setlocal

rem If backend_port.txt exists, use it. Otherwise default to 8765.
set "PORT_FILE=C:\Cue_extra\backend_port.txt"
set "CUE_BACKEND_PORT=8765"
if exist "%PORT_FILE%" (
  set /p CUE_BACKEND_PORT=<"%PORT_FILE%"
)

echo Using backend port: %CUE_BACKEND_PORT%

cd /d C:\Cue_repo\desktop

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