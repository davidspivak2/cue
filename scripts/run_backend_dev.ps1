# Backend dev runner with clean Ctrl+C handling:
# - No "Terminate batch job (Y/N)?" prompt
# - Window closes automatically when backend stops
# - Cue UI app is closed when backend receives Ctrl+C

$ErrorActionPreference = "Stop"
$LogDir = "C:\Cue_extra"
$LogFile = "$LogDir\backend_dev.log"
$PortFile = "$LogDir\backend_port.txt"
$BackendPort = 8765

$Repo = Split-Path $PSScriptRoot -Parent
if (-not $Repo) { $Repo = "C:\Cue_repo" }

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

# Write port without trailing newline
Set-Content -Path $PortFile -Value $BackendPort -NoNewline

Write-Host "Starting backend server on http://127.0.0.1:$BackendPort/health"
Write-Host "Example events URL: http://127.0.0.1:$BackendPort/jobs/{job_id}/events"
Write-Host "Logs: $LogFile"
Write-Host "Port file: $PortFile"

# Skip if backend already healthy
try {
    $r = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$BackendPort/health" -TimeoutSec 1
    if ($r.StatusCode -eq 200) {
        Write-Host "Backend already healthy on port $BackendPort. Not starting another instance."
        exit 0
    }
} catch {
    # Not running, continue
}

function Stop-CueApps {
    # Try graceful close first (like clicking X) to avoid cargo "process didn't exit successfully" error
    try {
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public class Native {
    [DllImport("user32.dll")]
    public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
}
'@ -ErrorAction Stop

        $WM_CLOSE = 0x0010
        $procs = Get-Process -Name "Cue", "cue-desktop" -ErrorAction SilentlyContinue
        foreach ($p in $procs) {
            if ($p.MainWindowHandle -ne [IntPtr]::Zero) {
                [Native]::PostMessage($p.MainWindowHandle, $WM_CLOSE, [IntPtr]::Zero, [IntPtr]::Zero) | Out-Null
            }
        }

        # Give app time to shut down cleanly; only force-kill if still running
        Start-Sleep -Seconds 2
        $afterCloseProcs = @(Get-Process -Name "Cue", "cue-desktop" -ErrorAction SilentlyContinue)
        if ($afterCloseProcs.Count -gt 0) {
            $afterCloseProcs | Stop-Process -Force
        }
    } catch { }
}

try {
    Push-Location $Repo
    # Use cmd to run Python so stderr (e.g. INFO logs) doesn't trigger PowerShell errors
    cmd /c "python -m app.backend_server > `"$LogFile`" 2>&1"
}
finally {
    Pop-Location
    Stop-CueApps
}
