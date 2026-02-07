param(
  [int]$VitePort = 5173
)

# Check if any process is listening on the Vite port (IPv4 or IPv6).
# If the listener is a Cue Vite dev server, stop it and recheck.

$listeners = Get-NetTCPConnection -LocalPort $VitePort -State Listen -ErrorAction SilentlyContinue |
  Select-Object -Property LocalAddress,LocalPort,OwningProcess

if (-not $listeners) {
  exit 0
}

$killPids = @()
foreach ($listener in $listeners) {
  $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)" -ErrorAction SilentlyContinue).CommandLine
  if ($cmd -and $cmd -like "*C:\Cue_repo\desktop*vite\bin\vite.js*") {
    $killPids += $listener.OwningProcess
  }
}
$killPids = @($killPids | Select-Object -Unique)

if ($killPids.Count -gt 0) {
  for ($i = 0; $i -lt $killPids.Count; $i++) {
    $targetPid = $killPids[$i]
    $proc = Get-Process -Id $targetPid -ErrorAction SilentlyContinue
    if ($proc) {
      Stop-Process -Id $targetPid -Force -ErrorAction SilentlyContinue
    }
    $stillRunning = Get-Process -Id $targetPid -ErrorAction SilentlyContinue
    if ($stillRunning) {
      & taskkill /PID $targetPid /T /F 2>&1 | Out-Null
    }
  }
}

# Recheck: is the port still in use?
$ipv4Open = Test-NetConnection -ComputerName 127.0.0.1 -Port $VitePort -InformationLevel Quiet
$ipv6Open = Test-NetConnection -ComputerName "::1" -Port $VitePort -InformationLevel Quiet

if ($ipv4Open -or $ipv6Open) {
  exit 1
}
exit 0
