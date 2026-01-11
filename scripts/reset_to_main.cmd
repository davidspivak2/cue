@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."
for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI"

echo [info] Using repo root: "%REPO_ROOT%"
cd /d "%REPO_ROOT%" || goto :die_cd

where git >nul 2>nul
if errorlevel 1 goto :die_git

echo [info] Current status:
git status

echo [warning] ============================================================
echo [warning] WARNING: This will discard ALL uncommitted changes.
echo [warning] ============================================================
set /p CONFIRM=Reset repository to origin/main? (Y/N): 
if /i not "%CONFIRM%"=="Y" (
  echo [info] Canceled.
  goto :done_ok
)

echo [info] Fetching latest changes...
git fetch origin
if errorlevel 1 goto :die_fetch

echo [info] Switching to main...
git switch main
if errorlevel 1 (
  git checkout main
  if errorlevel 1 goto :die_switch
)

echo [info] Resetting to origin/main...
git reset --hard origin/main
if errorlevel 1 goto :die_reset

set /p CLEAN=Remove untracked files with git clean -fd? (Y/N): 
if /i "%CLEAN%"=="Y" (
  echo [info] Removing untracked files...
  git clean -fd
  if errorlevel 1 goto :die_clean
)

call "%REPO_ROOT%\scripts\start_app.cmd"

:done_ok
pause
exit /b 0

:done_error
pause
exit /b 1

:die_cd
echo [error] Failed to change to repo root.
exit /b 1

:die_git
echo [error] Git is required but was not found in PATH.
exit /b 1

:die_fetch
echo [error] git fetch failed.
goto :done_error

:die_switch
echo [error] Failed to switch to main.
goto :done_error

:die_reset
echo [error] git reset failed.
goto :done_error

:die_clean
echo [error] git clean failed.
goto :done_error
