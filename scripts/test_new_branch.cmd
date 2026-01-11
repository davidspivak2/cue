@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"

echo [info] Using repo root: "%REPO_ROOT%"
cd /d "%REPO_ROOT%" || (echo [error] Failed to change to repo root.& exit /b 1)

echo [info] Fetching latest branches...
git fetch || (echo [error] git fetch failed.& exit /b 1)

set /p BRANCH=Enter branch to test (e.g. codex/...): 
if "%BRANCH%"=="" (
  echo Canceled.
  exit /b 1
)

set "LOCAL_REF=refs/heads/%BRANCH%"
set "REMOTE_REF=refs/remotes/origin/%BRANCH%"

git show-ref --verify --quiet "%LOCAL_REF%"
if errorlevel 1 (
  git show-ref --verify --quiet "%REMOTE_REF%"
  if errorlevel 1 (
    echo [error] Remote branch "origin/%BRANCH%" not found.
    exit /b 1
  )
  echo [info] Creating local tracking branch "%BRANCH%" from origin...
  git switch --track -c "%BRANCH%" "origin/%BRANCH%" || (echo [error] Failed to switch to branch.& exit /b 1)
) else (
  echo [info] Switching to existing local branch "%BRANCH%"...
  git switch "%BRANCH%" || (echo [error] Failed to switch to branch.& exit /b 1)
)

echo [info] Pulling latest changes (ff-only)...
git pull --ff-only
if errorlevel 1 (
  echo [warn] git pull failed. Continuing anyway.
)

call "%REPO_ROOT%\scripts\start_app.cmd" --no-pause

pause
endlocal
