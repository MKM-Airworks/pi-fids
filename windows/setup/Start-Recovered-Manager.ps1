param(
  [Parameter(Mandatory=$true)][string]$RecoveryFolder,
  [string]$ManagerRoot = "$env:LOCALAPPDATA\MKM\PiFidsManager",
  [int]$Port = 8810,
  [switch]$EnableLan,
  [switch]$OldManagerIsolated,
  [string]$LanAddress,
  [int]$LanPort = 8805
)
$ErrorActionPreference = 'Stop'
$python = Join-Path $ManagerRoot 'runtime\python.exe'
foreach ($name in @('manager.sqlite','manager-auth.json','manager-auth.users.json','site.json','recovery.json')) {
  if (!(Test-Path (Join-Path $RecoveryFolder $name))) { throw "Incomplete recovery folder: $name" }
}
if (!(Test-Path $python)) { throw 'Manager runtime not found.' }
if ($EnableLan -and (!$OldManagerIsolated -or !$LanAddress)) { throw 'Isolate the old manager and specify this PC LAN address before enabling the feed.' }
$arguments = @('-m','pifids','--database',(Join-Path $RecoveryFolder 'manager.sqlite'),'--auth-config',(Join-Path $RecoveryFolder 'manager-auth.json'),'--site-config',(Join-Path $RecoveryFolder 'site.json'),'--port',"$Port")
if ($EnableLan) { $arguments += @('--lan-host',$LanAddress,'--lan-port',"$LanPort") }
$web = Join-Path $RecoveryFolder 'web-connection.json'
if (Test-Path $web) { $arguments += @('--upstream-config',$web) }
$previousPath = $env:PYTHONPATH
try {
  $env:PYTHONPATH = Join-Path $ManagerRoot 'v2'
  Write-Host "Recovery manager: http://127.0.0.1:$Port/"
  Write-Host 'Keep this window open. Press Ctrl+C to stop. Automatic startup is not configured by this script.'
  & $python @arguments
  if ($LASTEXITCODE -ne 0) { throw 'Recovery manager stopped with an error.' }
} finally { $env:PYTHONPATH = $previousPath }
