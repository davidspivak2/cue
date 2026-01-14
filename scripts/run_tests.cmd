@echo off
chcp 65001 >nul
set PYTHONUTF8=1
setlocal EnableExtensions EnableDelayedExpansion

if not defined RUN_TESTS_FROM_TEMP (
  set "TEMP_SCRIPT=%TEMP%\run_tests_%RANDOM%_%RANDOM%.cmd"
  copy "%~f0" "%TEMP_SCRIPT%" >nul
  if errorlevel 1 (
    echo [error] Failed to copy script to temp.
    exit /b 1
  )
  set "RUN_TESTS_FROM_TEMP=1"
  call "%TEMP_SCRIPT%"
  set "EXIT_CODE=%errorlevel%"
  del "%TEMP_SCRIPT%" >nul 2>&1
  exit /b %EXIT_CODE%
)

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"

set "EXIT_CODE=0"
set "PUSHD_OK=0"
pushd "%REPO_ROOT%" || (
  echo [error] Failed to change to repo root.
  set "EXIT_CODE=1"
  goto :cleanup
)
set "PUSHD_OK=1"

echo [info] Using repo root: "%REPO_ROOT%"

set /p BRANCH=Enter branch to test (e.g. codex/...):
if "%BRANCH%"=="" (
  echo [error] Branch name is required.
  set "EXIT_CODE=1"
  goto :cleanup
)

for /f "delims=" %%G in ('git status --porcelain') do set "DIRTY=1"
if defined DIRTY (
  echo [error] Working tree has uncommitted changes. Please commit or stash before switching branches.
  set "EXIT_CODE=1"
  goto :cleanup
)

echo [info] Fetching latest branches...
git fetch origin
if errorlevel 1 (
  set "EXIT_CODE=%errorlevel%"
  goto :cleanup
)

echo [info] Switching to branch "%BRANCH%"...
git switch "%BRANCH%"
if errorlevel 1 (
  echo [info] Creating local tracking branch "%BRANCH%" from origin...
  git switch -c "%BRANCH%" --track "origin/%BRANCH%"
  if errorlevel 1 (
    set "EXIT_CODE=%errorlevel%"
    goto :cleanup
  )
)

echo [info] Pulling latest changes (ff-only)...
git pull --ff-only origin "%BRANCH%"
if errorlevel 1 (
  set "EXIT_CODE=%errorlevel%"
  goto :cleanup
)

set "VENV_PY=%REPO_ROOT%\.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
  echo [info] Creating virtual environment...
  call python -m venv ".venv"
  if errorlevel 1 (
    set "EXIT_CODE=%errorlevel%"
    goto :cleanup
  )
)

set "VENV_PY=%REPO_ROOT%\.venv\Scripts\python.exe"
echo [info] Upgrading pip...
call "%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 (
  set "EXIT_CODE=%errorlevel%"
  goto :cleanup
)

set "REQ_TXT=%REPO_ROOT%\requirements.txt"
set "REQ_DEV=%REPO_ROOT%\requirements-dev.txt"
if not exist "%REQ_TXT%" (
  echo [error] Missing requirements.txt at: "%REQ_TXT%"
  set "EXIT_CODE=1"
  goto :cleanup
)

echo [info] Using requirements: "%REQ_TXT%"
if exist "%REQ_DEV%" (
  echo [info] Using dev requirements: "%REQ_DEV%"
)

echo [info] Installing dependencies...
call "%VENV_PY%" -m pip install -r "%REQ_TXT%"
if errorlevel 1 (
  set "EXIT_CODE=%errorlevel%"
  goto :cleanup
)
if exist "%REQ_DEV%" (
  call "%VENV_PY%" -m pip install -r "%REQ_DEV%"
  if errorlevel 1 (
    set "EXIT_CODE=%errorlevel%"
    goto :cleanup
  )
  if errorlevel 1 (
    set "EXIT_CODE=%errorlevel%"
    goto :cleanup
  )
set "EXIT_CODE=%errorlevel%"

:cleanup
if "%PUSHD_OK%"=="1" popd
exit /b %EXIT_CODE%
equirements.txt"
  if errorlevel 1 exit /b %errorlevel%
  call "%VENV_PY%" -m pip install pytest
  if errorlevel 1 exit /b %errorlevel%
)

echo [info] Running tests...
call "%VENV_PY%" -m pytest
set "TEST_EXIT=%errorlevel%"
exit /b %TEST_EXIT%
