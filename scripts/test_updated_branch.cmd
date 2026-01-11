@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%.." || (echo [error] Failed to locate repo root.& exit /b 1)
set "REPO_ROOT=%CD%"
popd

echo [info] Using repo root: "%REPO_ROOT%"
cd /d "%REPO_ROOT%" || (echo [error] Failed to change to repo root.& exit /b 1)

for /f "delims=" %%B in ('git branch --show-current') do set "BRANCH=%%B"
if "%BRANCH%"=="" (
  echo [warn] Unable to determine current branch.
) else (
  echo [info] Current branch: "%BRANCH%"
)

echo [info] Pulling latest changes (ff-only)...
git pull --ff-only
if errorlevel 1 (
  echo [warn] git pull failed. Continuing anyway.
)

call "%REPO_ROOT%\scripts\start_app.cmd" --no-pause

pause
endlocal
