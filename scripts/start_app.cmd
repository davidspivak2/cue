@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"

echo [info] Using repo root: "%REPO_ROOT%"
cd /d "%REPO_ROOT%" || (echo [error] Failed to change to repo root.& exit /b 1)

set "INSTALL_MODE=auto"
set "PAUSE_AFTER=1"

:parse_args
if "%~1"=="" goto args_done
if /i "%~1"=="--install" set "INSTALL_MODE=force"
if /i "%~1"=="--no-install" set "INSTALL_MODE=skip"
if /i "%~1"=="--no-pause" set "PAUSE_AFTER=0"
shift
goto parse_args
:args_done

set "VENV_DIR=%REPO_ROOT%\.venv"
set "CREATED_VENV=0"

if not exist "%VENV_DIR%" (
  echo [info] Creating virtual environment at "%VENV_DIR%"...
  python -m venv "%VENV_DIR%" || (echo [error] Failed to create virtual environment.& exit /b 1)
  set "CREATED_VENV=1"
)

if not exist "%VENV_DIR%\Scripts\activate.bat" (
  echo [error] Virtual environment activation script not found at "%VENV_DIR%\Scripts\activate.bat".
  exit /b 1
)

call "%VENV_DIR%\Scripts\activate.bat" || (echo [error] Failed to activate virtual environment.& exit /b 1)

if /i "%INSTALL_MODE%"=="skip" (
  echo [info] Skipping dependency installation (--no-install).
) else (
  if "%CREATED_VENV%"=="1" (
    set "SHOULD_INSTALL=1"
  ) else if /i "%INSTALL_MODE%"=="force" (
    set "SHOULD_INSTALL=1"
  ) else (
    set "SHOULD_INSTALL=0"
  )

  if "%SHOULD_INSTALL%"=="1" (
    echo [info] Updating pip...
    python -m pip install --upgrade pip || (echo [error] Failed to upgrade pip.& exit /b 1)
    if exist "%REPO_ROOT%\requirements.txt" (
      echo [info] Installing dependencies from requirements.txt...
      python -m pip install -r "%REPO_ROOT%\requirements.txt" || (echo [error] Dependency installation failed.& exit /b 1)
    ) else if exist "%REPO_ROOT%\pyproject.toml" (
      echo [info] Installing dependencies from pyproject.toml...
      python -m pip install -e "%REPO_ROOT%" || (echo [error] Dependency installation failed.& exit /b 1)
    ) else (
      echo [info] No requirements.txt or pyproject.toml found. Skipping dependency installation.
    )
  ) else (
    echo [info] Using existing virtual environment. Dependency install not required.
  )
)

echo [info] Starting HebrewSubtitleGUI...
python -m app.main
if errorlevel 1 (
  echo [error] Application exited with an error.
  exit /b 1
)

if "%PAUSE_AFTER%"=="1" pause
endlocal
