@echo off
setlocal EnableExtensions

rem Repo root: scripts\local\ -> ..\..
set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%..\.."
for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI"

echo [info] Using repo root: "%REPO_ROOT%"
cd /d "%REPO_ROOT%" || goto :die_cd

where git >nul 2>nul
if errorlevel 1 goto :die_git

echo [info] Current status:
git status

set "BRANCH="
set /p BRANCH=Enter branch to test (e.g. codex/...):
if "%BRANCH%"=="" (
  echo [error] Branch name is required.
  goto :done_error
)

REM Run tests first (no pause), then start app only if tests pass
set "RUN_TESTS_NO_PAUSE=1"
call "%REPO_ROOT%\scripts\run_tests.cmd" "%BRANCH%"
set "TEST_EXIT=%ERRORLEVEL%"
set "RUN_TESTS_NO_PAUSE="

if not "%TEST_EXIT%"=="0" (
  echo [error] Tests failed. Not starting the app.
  goto :done_error
)

if exist "%SCRIPT_DIR%start_app.cmd" (
  call "%SCRIPT_DIR%start_app.cmd"
) else (
  call "%REPO_ROOT%\scripts\run_desktop_dev.cmd"
)
exit /b %ERRORLEVEL%

:done_error
pause
exit /b 1

:die_cd
echo [error] Failed to change to repo root.
pause
exit /b 1

:die_git
echo [error] Git is required but was not found in PATH.
pause
exit /b 1
