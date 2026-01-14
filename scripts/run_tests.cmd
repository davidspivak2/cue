@echo off
chcp 65001 >nul
set PYTHONUTF8=1
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================================================
REM Run from a temporary copy so branch switching cannot change the script mid-run
REM ============================================================================
if not defined RUN_TESTS_FROM_TEMP (
  set "ORIG_SCRIPT=%~f0"
  set "ORIG_SCRIPT_DIR=%~dp0"
  set "TMP_SCRIPT=%TEMP%\run_tests_!RANDOM!_!RANDOM!.cmd"

  copy /y "!ORIG_SCRIPT!" "!TMP_SCRIPT!" >nul
  if errorlevel 1 (
    echo [error] Failed to copy script to temp: "!TMP_SCRIPT!"
    exit /b 1
  )

  set "RUN_TESTS_FROM_TEMP=1"
  call "!TMP_SCRIPT!" %*
  set "RET=!ERRORLEVEL!"

  del /f /q "!TMP_SCRIPT!" >nul 2>nul
  exit /b !RET!
)

REM ==========================
REM Resolve repo root robustly
REM ==========================
if defined ORIG_SCRIPT_DIR (
  set "SCRIPT_DIR=%ORIG_SCRIPT_DIR%"
) else (
  set "SCRIPT_DIR=%~dp0"
)

for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"

pushd "%REPO_ROOT%" >nul
if errorlevel 1 (
  echo [error] Failed to change to repo root: "%REPO_ROOT%"
  exit /b 1
)

echo [info] Using repo root: "%REPO_ROOT%"

REM ====================
REM Prompt for the branch
REM ====================
set "BRANCH="
set /p BRANCH=Enter branch to test (e.g. codex/...):
if "%BRANCH%"=="" (
  echo [error] Branch name is required.
  set "TEST_EXIT=1"
  goto :cleanup
)

REM ============================
REM Safety: refuse dirty worktree
REM ============================
set "DIRTY="
for /f "delims=" %%G in ('git status --porcelain') do set "DIRTY=1"
if defined DIRTY (
  echo [error] Working tree has uncommitted changes. Please commit or stash before switching branches.
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
  echo [info] Creating local tracking branch "%BRANCH%" from origin...
  git switch -c "%BRANCH%" --track "origin/%BRANCH%"
  if errorlevel 1 (
    set "TEST_EXIT=1"
    goto :cleanup
  )
)

echo [info] Pulling latest changes (ff-only)...
git show-ref --verify --quiet "refs/remotes/origin/%BRANCH%"
if not errorlevel 1 (
  git pull --ff-only origin "%BRANCH%"
) else (
  git pull --ff-only
)
if errorlevel 1 (
  set "TEST_EXIT=1"
  goto :cleanup
)

REM ==================
REM Ensure venv + pip
REM ==================
set "VENV_DIR=%REPO_ROOT%\.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

if not exist "%VENV_PY%" (
  echo [info] Creating virtual environment...
  python -m venv "%VENV_DIR%"
  if errorlevel 1 (
    set "TEST_EXIT=1"
    goto :cleanup
  )
)

echo [info] Upgrading pip...
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 (
  set "TEST_EXIT=1"
  goto :cleanup
)

REM =========================
REM Install deps + run pytest
REM =========================
set "REQ_TXT=%REPO_ROOT%\requirements.txt"
set "REQ_DEV=%REPO_ROOT%\requirements-dev.txt"

if not exist "%REQ_TXT%" (
  echo [error] Missing requirements.txt at: "%REQ_TXT%"
  set "TEST_EXIT=1"
  goto :cleanup
)

echo [info] Installing dependencies...
echo [info] Using requirements: "%REQ_TXT%"

"%VENV_PY%" -m pip install -r "%REQ_TXT%"
if errorlevel 1 (
  set "TEST_EXIT=1"
  goto :cleanup
)

if exist "%REQ_DEV%" (
  echo [info] Using dev requirements: "%REQ_DEV%"
  "%
