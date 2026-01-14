@echo off
chcp 65001 >nul
set PYTHONUTF8=1
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."
for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI"

cd /d "%REPO_ROOT%" || (
  echo [error] Failed to change to repo root.
  exit /b 1
)

echo [info] Using repo root: "%REPO_ROOT%"

set /p BRANCH=Enter branch to test (e.g. codex/...):
if "%BRANCH%"=="" (
  echo [error] Branch name is required.
  exit /b 1
)

for /f "delims=" %%G in ('git status --porcelain') do set "DIRTY=1"
if defined DIRTY (
  echo [error] Working tree has uncommitted changes. Please commit or stash before switching branches.
  exit /b 1
)

echo [info] Fetching latest branches...
git fetch origin
if errorlevel 1 exit /b %errorlevel%

echo [info] Switching to branch "%BRANCH%"...
git switch "%BRANCH%"
if errorlevel 1 (
  echo [info] Creating local tracking branch "%BRANCH%" from origin...
  git switch -c "%BRANCH%" --track "origin/%BRANCH%"
  if errorlevel 1 exit /b %errorlevel%
)

echo [info] Pulling latest changes (ff-only)...
git pull --ff-only
if errorlevel 1 exit /b %errorlevel%

set "VENV_PY=%REPO_ROOT%\.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
  echo [info] Creating virtual environment...
  call python -m venv ".venv"
  if errorlevel 1 exit /b %errorlevel%
)

set "VENV_PY=%REPO_ROOT%\.venv\Scripts\python.exe"
echo [info] Upgrading pip...
call "%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 exit /b %errorlevel%

echo [info] Installing dependencies...
if exist "%REPO_ROOT%equirements-dev.txt" (
  call "%VENV_PY%" -m pip install -r "%REPO_ROOT%equirements.txt"
  if errorlevel 1 exit /b %errorlevel%
  call "%VENV_PY%" -m pip install -r "%REPO_ROOT%equirements-dev.txt"
  if errorlevel 1 exit /b %errorlevel%
) else (
  call "%VENV_PY%" -m pip install -r "%REPO_ROOT%equirements.txt"
  if errorlevel 1 exit /b %errorlevel%
  call "%VENV_PY%" -m pip install pytest
  if errorlevel 1 exit /b %errorlevel%
)

echo [info] Running tests...
call "%VENV_PY%" -m pytest
set "TEST_EXIT=%errorlevel%"
exit /b %TEST_EXIT%
