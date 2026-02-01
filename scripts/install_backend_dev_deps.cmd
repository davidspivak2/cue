@echo off
setlocal

set "LOG_DIR=C:\Cue_extra"
set "LOG_FILE=%LOG_DIR%\backend_deps_install.log"

if not exist "%LOG_DIR%" (
  mkdir "%LOG_DIR%"
)

echo Using Python executable: > "%LOG_FILE%"
python -c "import sys; print(sys.executable)" >> "%LOG_FILE%" 2>&1
echo. >> "%LOG_FILE%"
echo Pip version: >> "%LOG_FILE%"
python -m pip --version >> "%LOG_FILE%" 2>&1
echo. >> "%LOG_FILE%"
echo Installing backend dev dependencies... >> "%LOG_FILE%"
python -m pip install -r "%~dp0\..\requirements-backend-dev.txt" >> "%LOG_FILE%" 2>&1

echo.
echo Backend dependency install complete. Log saved to:
echo %LOG_FILE%
echo.
endlocal
