@echo off
setlocal
rem Keep the console open after the script ends:
rem - Double-click / some hosts use cmd /c and close when the batch exits; "pause" also fails if stdin is redirected.
rem - We re-launch under cmd /k unless CI is set or you pass: norespawn
if /i "%~1"=="norespawn" (
  shift
  goto :main
)
if /i "%~1"=="_KEEPOPEN" (
  shift
  goto :main
)
if defined CI goto :main
if defined TF_BUILD goto :main
for %%A in ("%~f0") do (
  "%ComSpec%" /k pushd "%%~dpA.." ^& title Cue release build ^& call "%%~dpA%~nx0" _KEEPOPEN
)
exit /b 0

:main
set "REPO=%CD%"
if not exist "%REPO%\scripts\build_engine.cmd" (
  echo [ERROR] Invalid repo root: "%REPO%"
  echo        Expected: ^<repo^>\scripts\build_engine.cmd
  pause
  exit /b 1
)

echo [INFO] Building packaged backend engine...
call "%REPO%\scripts\build_engine.cmd"
if errorlevel 1 (
  echo [ERROR] Engine build failed.
  pause
  exit /b 1
)

echo [INFO] Building Tauri installers...
cd /d "%REPO%\desktop"
if errorlevel 1 (
  echo [ERROR] Could not open desktop folder.
  pause
  exit /b 1
)

rem Remove prior NSIS outputs so makensis is not blocked by a locked .exe (AV, Explorer, or a running installer).
call :clean_nsis_outputs

set "MSI_ONLY_FALLBACK=0"
call npm run tauri build
if errorlevel 1 goto :tauri_retry_after_fail
goto :tauri_after_retry

:tauri_retry_after_fail
rem NOTE: Do not use "call :clean_nsis_outputs" inside a parenthesized IF block; cmd.exe often fails to resolve the label.
echo [WARN] First Tauri build failed. Retrying once after NSIS cleanup and a short delay ^(often fixes "Access is denied" / error 5^)...
call :clean_nsis_outputs
timeout /t 3 /nobreak >nul
call npm run tauri build

:tauri_after_retry
if errorlevel 1 goto :tauri_msi_fallback
goto :after_subs

:tauri_msi_fallback
echo [WARN] Full Tauri installer build failed. Retrying MSI-only build...
echo [HELP] If NSIS failed with "Access is denied" ^(os error 5^): close any Explorer window on bundle\nsis,
echo        quit a running Cue setup.exe from that folder, wait for antivirus to finish, then run this script again.
set "MSI_ONLY_FALLBACK=1"
call npm run tauri build -- --bundles msi
if errorlevel 1 (
  echo [ERROR] Tauri build failed.
  pause
  exit /b 1
)
goto :after_subs

:clean_nsis_outputs
rem Final bundle output (typical lock target)
if exist "%REPO%\desktop\src-tauri\target\release\bundle\nsis" (
  del /f /q "%REPO%\desktop\src-tauri\target\release\bundle\nsis\*.exe" 2>nul
)
rem Intermediate makensis output directory
if exist "%REPO%\desktop\src-tauri\target\release\nsis" (
  del /f /s /q "%REPO%\desktop\src-tauri\target\release\nsis\*.exe" 2>nul
)
exit /b 0

:after_subs

echo.
echo [OK] Release build complete.
if "%MSI_ONLY_FALLBACK%"=="1" (
  echo [WARN] NSIS build did not complete in this run. MSI bundle was generated as fallback.
)
echo [OK] NSIS installers: %REPO%\desktop\src-tauri\target\release\bundle\nsis
echo [OK] MSI installers:  %REPO%\desktop\src-tauri\target\release\bundle\msi
echo.
if defined CI exit /b 0
if defined TF_BUILD exit /b 0
echo This window stays open - type EXIT and press Enter when you are finished.
exit /b 0
