@echo off
chcp 65001 >nul
set PYTHONUTF8=1
setlocal EnableExtensions

REM If RUN_TESTS_NO_PAUSE is set to 1, skip pausing at the end.
if not defined RUN_TESTS_NO_PAUSE set "RUN_TESTS_NO_PAUSE=0"

REM ============================================================================
REM Run from a temporary copy so branch switching cannot change the script mid-run
REM (implemented without parenthesis blocks to avoid cmd parser issues)
REM ============================================================================
if defined RUN_TESTS_FROM_TEMP goto :main

set "ORIG_SCRIPT=%~f0"
set "ORIG_SCRIPT_DIR=%~dp0"
set "TMP_SCRIPT=%TEMP%\run_tests_%RANDOM%_%RANDOM%.cmd"

copy /y "%ORIG_SCRIPT%" "%TMP_SCRIPT%" >nul
if errorlevel 1 (
  echo [error] Failed to copy script to temp: "%TMP_SCRIPT%"
  exit /b 1
)

set "RUN_TESTS_FROM_TEMP=1"
call "%TMP_SCRIPT%" %*
set "RET=%ERRORLEVEL%"

del /f /q "%TMP_SCRIPT%" >nul 2>nul
exit /b %RET%

:main
set "TEST_EXIT=0"

REM ==========================
REM Resolve repo root robustly
REM ==========================
REM Script is in <repo>\scripts\, so repo root is one level up from this file's directory
for %%I in ("%ORIG_SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"

pushd "%REPO_ROOT%" >nul
if errorlevel 1 (
  echo [error] Failed to change to repo root: "%REPO_ROOT%"
  exit /b 1
)

echo [info] Using repo root: "%REPO_ROOT%"

REM ====================
REM Basic tool checks
REM ====================
where git >nul 2>nul
if errorlevel 1 (
  echo [error] Git not found in PATH.
  set "TEST_EXIT=1"
  goto :cleanup
)

set "PY_CMD=python"
where python >nul 2>nul
if errorlevel 1 (
  where py >nul 2>nul
  if errorlevel 1 (
    echo [error] Python not found in PATH. Need python or py launcher.
    set "TEST_EXIT=1"
    goto :cleanup
  )
  set "PY_CMD=py"
)

REM ====================
REM Ask which branch
REM ====================
set "BRANCH="
set /p BRANCH=Enter branch to test (example: codex/...):
if "%BRANCH%"=="" (
  echo [error] Branch name is required.
  set "TEST_EXIT=1"
  goto :cleanup
)

REM ============================
REM Safety: refuse dirty worktree
REM ============================
set "DIRTY="
for /f "delims=" %%G in ('git status --porcelain') do (
  set "DIRTY=1"
  goto :dirty_done
)
:dirty_done
if defined DIRTY (
  echo [error] Working tree has uncommitted changes. Commit or stash before switching branches.
  set "TEST_EXIT=1"
  goto :cleanup
)

REM ===========
REM Git actions
REM ===========
echo [info] Fetching latest branches...
git fetch origin
if errorlevel 1 (
  set "TEST_EXIT=1"
  goto :cleanup
)

echo [info] Switching to branch "%BRANCH%"...
git switch "%BRANCH%"
if errorlevel 1 (
  echo [info] Local branch not found; creating tracking branch from origin...
  git switch -c "%BRANCH%" --track "origin/%BRANCH%"
  if errorlevel 1 (
    set "TEST_EXIT=1"
    goto :cleanup
  )
)

echo [info] Pulling latest changes (ff-only)...
git pull --ff-only
if errorlevel 1 (
  git pull --ff-only origin "%BRANCH%"
  if errorlevel 1 (
    set "TEST_EXIT=1"
    goto :cleanup
  )
)

REM ==================
REM Ensure venv
REM ==================
set "VENV_DIR=%REPO_ROOT%\.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

if not exist "%VENV_PY%" (
  echo [info] Creating virtual environment...
  "%PY_CMD%" -m venv "%VENV_DIR%"
  if errorlevel 1 (
    set "TEST_EXIT=1"
    goto :cleanup
  )
)

if not exist "%VENV_PY%" (
  echo [error] Venv python not found at "%VENV_PY%".
  set "TEST_EXIT=1"
  goto :cleanup
)

REM =====================================
REM Install deps only if requirements changed
REM =====================================
set "REQ_TXT=%REPO_ROOT%\requirements.txt"
set "REQ_DEV=%REPO_ROOT%\requirements-dev.txt"
set "MARK_REQ=%VENV_DIR%\.requirements_sha256.txt"
set "MARK_DEV=%VENV_DIR%\.requirements_dev_sha256.txt"

if not exist "%REQ_TXT%" (
  echo [error] Missing requirements.txt at: "%REQ_TXT%"
  set "TEST_EXIT=1"
  goto :cleanup
)

call :hash_file "%REQ_TXT%"
if errorlevel 1 (
  echo [error] Failed to hash "%REQ_TXT%".
  set "TEST_EXIT=1"
  goto :cleanup
)
set "NEW_REQ_HASH=%OUT_HASH%"

set "OLD_REQ_HASH="
if exist "%MARK_REQ%" set /p OLD_REQ_HASH=<"%MARK_REQ%"

if /i "%NEW_REQ_HASH%"=="%OLD_REQ_HASH%" goto :req_ok

echo [info] requirements.txt changed (or first run). Installing...
call :upgrade_pip_once
if errorlevel 1 (
  set "TEST_EXIT=1"
  goto :cleanup
)

"%VENV_PY%" -m pip install -r "%REQ_TXT%"
if errorlevel 1 (
  set "TEST_EXIT=1"
  goto :cleanup
)

> "%MARK_REQ%" echo %NEW_REQ_HASH%

:req_ok
echo [info] requirements.txt up-to-date.

if exist "%REQ_DEV%" goto :dev_present

REM Dev file missing -> remove dev marker and ensure pytest exists
if exist "%MARK_DEV%" del /q "%MARK_DEV%" >nul 2>nul

"%VENV_PY%" -m pip show pytest >nul 2>nul
if not errorlevel 1 goto :dev_done

echo [info] requirements-dev.txt not found; installing pytest...
call :upgrade_pip_once
if errorlevel 1 (
  set "TEST_EXIT=1"
  goto :cleanup
)

"%VENV_PY%" -m pip install pytest
if errorlevel 1 (
  set "TEST_EXIT=1"
  goto :cleanup
)
goto :dev_done

:dev_present
call :hash_file "%REQ_DEV%"
if errorlevel 1 (
  echo [error] Failed to hash "%REQ_DEV%".
  set "TEST_EXIT=1"
  goto :cleanup
)
set "NEW_DEV_HASH=%OUT_HASH%"

set "OLD_DEV_HASH="
if exist "%MARK_DEV%" set /p OLD_DEV_HASH=<"%MARK_DEV%"

if /i "%NEW_DEV_HASH%"=="%OLD_DEV_HASH%" goto :dev_done

echo [info] requirements-dev.txt changed (or first run). Installing...
call :upgrade_pip_once
if errorlevel 1 (
  set "TEST_EXIT=1"
  goto :cleanup
)

"%VENV_PY%" -m pip install -r "%REQ_DEV%"
if errorlevel 1 (
  set "TEST_EXIT=1"
  goto :cleanup
)

> "%MARK_DEV%" echo %NEW_DEV_HASH%

:dev_done
echo [info] Dev/test deps up-to-date.

echo [info] Running tests...
"%VENV_PY%" -m pytest
set "TEST_EXIT=%ERRORLEVEL%"

:cleanup
popd >nul
if "%RUN_TESTS_NO_PAUSE%"=="0" (
  echo.
  echo [info] Done. Exit code: %TEST_EXIT%
  pause
)
exit /b %TEST_EXIT%

REM ==========================
REM Helpers
REM ==========================

:upgrade_pip_once
if defined PIP_UPGRADED exit /b 0
echo [info] Upgrading pip...
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
set "PIP_UPGRADED=1"
exit /b 0

:hash_file
set "OUT_HASH="
for /f "tokens=1" %%H in ('certutil -hashfile "%~1" SHA256 ^| findstr /R /I "^[0-9A-F][0-9A-F]*$"') do (
  set "OUT_HASH=%%H"
  goto :hash_done
)
:hash_done
if not defined OUT_HASH exit /b 1
exit /b 0
