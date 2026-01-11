@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."
for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI"

echo [info] Using repo root: "%REPO_ROOT%"
cd /d "%REPO_ROOT%" || goto :die_cd

set "INSTALL_MODE=auto"
set "PAUSE_AFTER=1"

:parse_args
if "%~1"=="" goto args_done
if /i "%~1"=="--install" set "INSTALL_MODE=force"
if /i "%~1"=="--no-install" set "INSTALL_MODE=skip"
if /i "%~1"=="--no-pause" set "PAUSE_AFTER=0"
if /i "%~1"=="--help" goto :usage
shift
goto parse_args
:args_done

where git >nul 2>nul
if errorlevel 1 goto :die_git

set "PY_CMD=python"
where python >nul 2>nul
if errorlevel 1 (
  where py >nul 2>nul
  if errorlevel 1 goto :die_python
  set "PY_CMD=py"
)

set "VENV_DIR=%REPO_ROOT%\.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "CREATED_VENV=0"

if not exist "%VENV_PY%" (
  echo [info] Creating virtual environment at "%VENV_DIR%"...
  "%PY_CMD%" -m venv "%VENV_DIR%"
  if errorlevel 1 goto :die_venv
  set "CREATED_VENV=1"
)

if not exist "%VENV_PY%" goto :die_venv_missing

set "SHOULD_INSTALL=0"
if /i "%INSTALL_MODE%"=="force" set "SHOULD_INSTALL=1"
if /i "%INSTALL_MODE%"=="skip" set "SHOULD_INSTALL=0"
if "%CREATED_VENV%"=="1" set "SHOULD_INSTALL=1"

if "%SHOULD_INSTALL%"=="1" (
  echo [info] Updating pip...
  "%VENV_PY%" -m pip install --upgrade pip
  if errorlevel 1 goto :die_pip
  if exist "%REPO_ROOT%\requirements.txt" (
    echo [info] Installing dependencies from requirements.txt...
    "%VENV_PY%" -m pip install -r "%REPO_ROOT%\requirements.txt"
    if errorlevel 1 goto :die_deps
  ) else if exist "%REPO_ROOT%\pyproject.toml" (
    echo [info] Installing dependencies from pyproject.toml...
    "%VENV_PY%" -m pip install -e "%REPO_ROOT%"
    if errorlevel 1 goto :die_deps
  ) else (
    echo [info] No requirements.txt or pyproject.toml found. Skipping dependency installation.
  )
) else (
  echo [info] Using existing virtual environment. Dependency install not required.
)

echo [info] Starting HebrewSubtitleGUI...
"%VENV_PY%" -m app.main
set "APP_EXIT=%ERRORLEVEL%"
if %APP_EXIT% NEQ 0 (
  echo [error] Application exited with an error.
)

if "%PAUSE_AFTER%"=="1" pause
exit /b %APP_EXIT%

:usage
echo Usage: start_app.cmd [--install] [--no-install] [--no-pause] [--help]
exit /b 0

:die_cd
echo [error] Failed to change to repo root.
exit /b 1

:die_git
echo [error] Git is required but was not found in PATH.
exit /b 1

:die_python
echo [error] Python is required but was not found in PATH.
exit /b 1

:die_venv
echo [error] Failed to create virtual environment.
exit /b 1

:die_venv_missing
echo [error] Virtual environment python not found at "%VENV_PY%".
exit /b 1

:die_pip
echo [error] Failed to upgrade pip.
exit /b 1

:die_deps
echo [error] Dependency installation failed.
exit /b 1
