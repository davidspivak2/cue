@echo off
setlocal enabledelayedexpansion

if not exist .venv\Scripts\activate.bat (
  echo [INFO] Creating virtual environment...
  python -m venv .venv
  if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    exit /b 1
  )
)

call .venv\Scripts\activate.bat

python -m pip install --upgrade pip
if errorlevel 1 (
  echo [ERROR] Failed to upgrade pip.
  exit /b 1
)

python -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] Failed to install requirements.
  exit /b 1
)

python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
  python -m pip install pyinstaller
  if errorlevel 1 (
    echo [ERROR] Failed to install PyInstaller.
    exit /b 1
  )
)
pyinstaller --version >nul 2>&1
if errorlevel 1 (
  echo [ERROR] PyInstaller is not available after install.
  exit /b 1
)

if not exist bin mkdir bin

set "FFMPEG_EXE="
set "FFPROBE_EXE="
for /f "delims=" %%F in ('where ffmpeg 2^>nul') do if not defined FFMPEG_EXE set "FFMPEG_EXE=%%F"
for /f "delims=" %%F in ('where ffprobe 2^>nul') do if not defined FFPROBE_EXE set "FFPROBE_EXE=%%F"

if not exist bin\ffmpeg.exe (
  if defined FFMPEG_EXE (
    copy /Y "%FFMPEG_EXE%" "bin\ffmpeg.exe" >nul
  )
)

if not exist bin\ffprobe.exe (
  if defined FFPROBE_EXE (
    copy /Y "%FFPROBE_EXE%" "bin\ffprobe.exe" >nul
  )
)

if not exist bin\ffmpeg.exe (
  call download_ffmpeg.bat
  if errorlevel 1 (
    echo [ERROR] download_ffmpeg.bat failed.
    exit /b 1
  )
)

if not exist bin\ffprobe.exe (
  call download_ffmpeg.bat
  if errorlevel 1 (
    echo [ERROR] download_ffmpeg.bat failed.
    exit /b 1
  )
)

if not exist bin\ffmpeg.exe (
  echo [ERROR] FFmpeg is missing. Run download_ffmpeg.bat or install via winget: winget install -e --id Gyan.FFmpeg
  exit /b 1
)

if not exist bin\ffprobe.exe (
  echo [ERROR] FFprobe is missing. Run download_ffmpeg.bat or install via winget: winget install -e --id Gyan.FFmpeg
  exit /b 1
)

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

pyinstaller --noconfirm HebrewSubtitleGUI.spec

if errorlevel 1 (
  echo [ERROR] PyInstaller failed.
  exit /b 1
)

set "INTERNAL_DIR=dist\HebrewSubtitleGUI\_internal"
if exist "%INTERNAL_DIR%" (
  echo [INFO] Scanning for OpenMP DLL duplicates...
  set "KEEP_OMP_DLL="
  for /f "delims=" %%F in ('dir /b /s "%INTERNAL_DIR%\libiomp5md.dll" 2^>nul') do (
    if not defined KEEP_OMP_DLL (
      set "KEEP_OMP_DLL=%%F"
      echo [INFO] Keeping %%F
    ) else (
      echo [INFO] Removing duplicate %%F
      del /f /q "%%F" >nul 2>&1
    )
  )
)

echo Build complete. Output in dist\HebrewSubtitleGUI\HebrewSubtitleGUI.exe
