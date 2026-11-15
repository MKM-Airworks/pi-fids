param(
  [Parameter(Mandatory=$true)][string]$Backup,
  [Parameter(Mandatory=$true)][string]$Airport,
  [Parameter(Mandatory=$true)][string]$Output,
  [string]$ManagerRoot = "$env:LOCALAPPDATA\MKM\PiFidsManager"
)
$ErrorActionPreference = 'Stop'
$python = Join-Path $ManagerRoot 'runtime\python.exe'
if (!(Test-Path $python)) { throw 'Manager runtime not found. Install the current manager package first.' }
if (Test-Path $Output) { throw 'Choose a new recovery folder. Existing folders will not be overwritten.' }
$previousPath = $env:PYTHONPATH
try {
  $env:PYTHONPATH = Join-Path $ManagerRoot 'v2'
  & $python -m pifids.backup $Backup --airport $Airport --output $Output
  if ($LASTEXITCODE -ne 0) { throw 'Recovery validation failed. Live data was not changed.' }
} finally { $env:PYTHONPATH = $previousPath }
