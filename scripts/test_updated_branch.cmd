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

set /p BRANCH=Enter branch to test: 
if "%BRANCH%"=="" (
  echo [error] Branch name is required.
  goto :done_error
)

echo [info] Fetching latest branches...
git fetch origin
if errorlevel 1 goto :die_fetch

echo [info] Switching to "%BRANCH%"...
git switch "%BRANCH%"
if errorlevel 1 goto :die_switch

echo [info] Pulling latest changes...
git pull
if errorlevel 1 goto :die_pull

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
echo [error] Failed to switch to branch "%BRANCH%".
goto :done_error

:die_pull
echo [error] git pull failed.
goto :done_error
