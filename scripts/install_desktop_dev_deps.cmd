@echo off
setlocal

cd /d C:\Cue_repo\desktop

if exist package-lock.json (
  echo Installing desktop deps via npm ci...
  npm ci
) else (
  echo Installing desktop deps via npm install...
  npm install
)

echo Done.