@echo off
setlocal enabledelayedexpansion

if not exist .venv\Scripts\activate.bat (
  echo [ERROR] .venv not found. Create it with: python -m venv .venv
  exit /b 1
)

call .venv\Scripts\activate.bat

if not exist bin\ffmpeg.exe (
  echo [ERROR] Missing bin\ffmpeg.exe
  echo Run download_ffmpeg.bat or place ffmpeg.exe in bin\
  exit /b 1
)

if not exist bin\ffprobe.exe (
  echo [ERROR] Missing bin\ffprobe.exe
  echo Run download_ffmpeg.bat or place ffprobe.exe in bin\
  exit /b 1
)

pyinstaller --noconfirm --windowed --name HebrewSubtitleGUI ^
  --add-binary "bin\ffmpeg.exe;bin" ^
  --add-binary "bin\ffprobe.exe;bin" ^
  --collect-all faster_whisper ^
  --collect-all ctranslate2 ^
  app\main.py

if %ERRORLEVEL% NEQ 0 (
  echo [ERROR] PyInstaller failed.
  exit /b %ERRORLEVEL%
)

echo Build complete. Output in dist\HebrewSubtitleGUI\HebrewSubtitleGUI.exe
