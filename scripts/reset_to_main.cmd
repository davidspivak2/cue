@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%.." || (echo [error] Failed to locate repo root.& exit /b 1)
set "REPO_ROOT=%CD%"
popd

echo [warning] ============================================================
echo [warning] WARNING: This will discard ALL uncommitted changes and
echo [warning] delete ALL untracked files. This action is destructive.
echo [warning] ============================================================

choice /c YN /m "Reset repository to origin/main?"
if errorlevel 2 (
  echo Canceled.
  exit /b 0
)

echo [info] Using repo root: "%REPO_ROOT%"
cd /d "%REPO_ROOT%" || (echo [error] Failed to change to repo root.& exit /b 1)

echo [info] Fetching latest changes...
git fetch || (echo [error] git fetch failed.& exit /b 1)

echo [info] Switching to main...
git switch main || (echo [error] Failed to switch to main.& exit /b 1)

echo [info] Resetting to origin/main...
git reset --hard origin/main || (echo [error] git reset failed.& exit /b 1)

echo [info] Removing untracked files...
git clean -fd || (echo [error] git clean failed.& exit /b 1)

call "%REPO_ROOT%\scripts\start_app.cmd" --no-pause

pause
endlocal
