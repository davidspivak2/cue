@echo off
setlocal

for %%I in ("%~dp0..") do set "REPO=%%~fI"

echo [INFO] Building packaged backend engine...
call "%REPO%\scripts\build_engine.cmd"
if errorlevel 1 (
  echo [ERROR] Engine build failed.
  exit /b 1
)

echo [INFO] Building Tauri installers...
cd /d "%REPO%\desktop"
if errorlevel 1 (
  echo [ERROR] Could not open desktop folder.
  exit /b 1
)

set "MSI_ONLY_FALLBACK=0"
call npm run tauri build
if errorlevel 1 (
  echo [WARN] Full Tauri installer build failed. Retrying MSI-only build...
  set "MSI_ONLY_FALLBACK=1"
  call npm run tauri build -- --bundles msi
  if errorlevel 1 (
    echo [ERROR] Tauri build failed.
    exit /b 1
  )
)

echo.
echo [OK] Release build complete.
if "%MSI_ONLY_FALLBACK%"=="1" (
  echo [WARN] NSIS build did not complete in this run. MSI bundle was generated as fallback.
)
echo [OK] NSIS installers: %REPO%\desktop\src-tauri\target\release\bundle\nsis
echo [OK] MSI installers:  %REPO%\desktop\src-tauri\target\release\bundle\msi
exit /b 0
