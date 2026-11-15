param(
 [string]$Root=$PSScriptRoot,
 [ValidateRange(1024,65535)][int]$Port=8801,
 [string]$ProfileDirectory='',
 [ValidateRange(1,300)][int]$PollSeconds=10,
 [switch]$CheckOnly
)
# Windows PowerShell 5.1. Cold HDDs/Windows servicing may delay either process.
$ErrorActionPreference='Stop'
$Root=[IO.Path]::GetFullPath($Root)
$log=Join-Path $Root 'display-startup.log'
function Write-StartupLog([string]$Message){
 try{
  if((Test-Path $log) -and (Get-Item $log).Length -gt 1MB){Move-Item $log ($log+'.1') -Force}
  Add-Content -LiteralPath $log -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss')+' '+$Message) -Encoding UTF8
 }catch{Write-Warning 'Could not write display-startup.log'}
}
function Test-ReceiverReady($Config){
 # A listening socket alone is insufficient. Cached offline display IS valid.
 try{
  $airport=[Uri]::EscapeDataString($Config.airport)
  $id=[Uri]::EscapeDataString($Config.displayId)
  $state=Invoke-RestMethod "http://127.0.0.1:$Port/api/state?airport=$airport" -TimeoutSec 5
  if($state.airport -ne $Config.airport){return $false}
  $control=Invoke-RestMethod "http://127.0.0.1:$Port/api/display?airport=$airport&displayId=$id" -TimeoutSec 5
  return $control.displayId -eq $Config.displayId
 }catch{return $false}
}
function Get-KioskWindow{
 # Match this session and dedicated profile, never a personal Edge window.
 $session=[Diagnostics.Process]::GetCurrentProcess().SessionId
 foreach($item in @(Get-CimInstance Win32_Process -Filter "name='msedge.exe'")){
  if($item.SessionId -ne $session -or -not $item.CommandLine){continue}
  if($item.CommandLine.IndexOf($ProfileDirectory,[StringComparison]::OrdinalIgnoreCase) -lt 0 -or $item.CommandLine -notmatch '(?:^|\s)--kiosk(?:\s|$)'){continue}
  $process=Get-Process -Id $item.ProcessId -ErrorAction SilentlyContinue
  if($process -and $process.MainWindowHandle -ne [IntPtr]::Zero){return $process}
 }
 return $null
}
# Only one startup worker per installation/session, including shortcut clicks.
$hash=[Security.Cryptography.SHA256]::Create()
try{$key=([BitConverter]::ToString($hash.ComputeHash([Text.Encoding]::UTF8.GetBytes($Root.ToLowerInvariant()+':'+$Port)))).Replace('-','')}finally{$hash.Dispose()}
$mutex=New-Object Threading.Mutex($false,('Local\PiFidsDisplayStartup-'+$key))
$owned=$false
try{
 try{$owned=$mutex.WaitOne(0)}catch [Threading.AbandonedMutexException]{$owned=$true}
 if(-not $owned){exit 0}
 Write-StartupLog 'Startup worker started; waiting for the local receiver.'
 $config=Get-Content -LiteralPath (Join-Path $Root 'data\connection.json') -Raw | ConvertFrom-Json
 if($config.airport -notmatch '^[A-Z]{3}$' -or $config.displayId -notmatch '^[A-Za-z0-9_-]{1,40}$'){throw 'Invalid terminal identity in connection.json'}
 if(-not $ProfileDirectory){$ProfileDirectory=Join-Path $Root 'edge-kiosk'}
 $ProfileDirectory=[IO.Path]::GetFullPath($ProfileDirectory)
 $candidates=@("$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe","$env:LOCALAPPDATA\Microsoft\Edge\Application\msedge.exe")
 if(${env:ProgramFiles(x86)}){$candidates+="${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"}
 $edge=$candidates | Where-Object {Test-Path -LiteralPath $_} | Select-Object -First 1
 if(-not $edge -and -not $CheckOnly){throw 'Microsoft Edge is required'}
 $nextLog=[DateTime]::MinValue
 while(-not (Test-ReceiverReady $config)){
  if([DateTime]::UtcNow -ge $nextLog){Write-StartupLog 'Receiver is not ready; retrying (upstream online status is not required).';$nextLog=[DateTime]::UtcNow.AddMinutes(1)}
  Start-Sleep -Seconds $PollSeconds
 }
 Write-StartupLog 'Receiver HTTP responses and terminal identity verified.'
 if($CheckOnly){Write-StartupLog 'Readiness check passed; browser launch skipped.';exit 0}
 $url="http://127.0.0.1:$Port/display?airport=$($config.airport)&displayId=$($config.displayId)&kiosk=1"
 $nextLaunch=[DateTime]::MinValue
 $nextLog=[DateTime]::MinValue
 while($true){
  try{
   $window=Get-KioskWindow
   if($window){
    $hidden=$false
    for($attempt=0;$attempt -lt 3 -and -not $hidden;$attempt++){
     try{& (Join-Path $Root 'Hide-Taskbar.ps1');$hidden=$true}catch{Write-StartupLog 'Taskbar is not ready; retrying.';Start-Sleep -Seconds $PollSeconds}
    }
    if(-not $hidden){throw 'Taskbar initialization is still pending'}
    $shell=New-Object -ComObject WScript.Shell
    $shell.AppActivate([int]$window.Id) | Out-Null
    Write-StartupLog 'Kiosk window is open; startup completed.'
    break
   }
   if([DateTime]::UtcNow -ge $nextLaunch -and (Test-ReceiverReady $config)){
    $launch=Start-Process -FilePath $edge -WorkingDirectory (Split-Path $edge -Parent) -WindowStyle Normal -PassThru -ArgumentList @('--kiosk',('"'+$url+'"'),'--edge-kiosk-type=fullscreen','--no-first-run',('--user-data-dir="'+$ProfileDirectory+'"'))
    # Reissue to the SAME profile only. Never kill personal Edge processes.
    $nextLaunch=[DateTime]::UtcNow.AddMinutes(5)
    Write-StartupLog 'Edge launch requested; waiting for its kiosk window.'
    Start-Sleep -Seconds 2
    $launch.Refresh()
    if($launch.HasExited){Write-StartupLog ('Edge launcher exited with code '+$launch.ExitCode+'; verifying the kiosk window.');$nextLaunch=[DateTime]::UtcNow.AddSeconds(30)}
   }
  }catch{Write-StartupLog 'Browser/shell startup is not ready; retrying without changing saved data.';Start-Sleep -Seconds $PollSeconds}
  if([DateTime]::UtcNow -ge $nextLog){Write-StartupLog 'Waiting for the kiosk window; startup retry remains active.';$nextLog=[DateTime]::UtcNow.AddMinutes(1)}
  Start-Sleep -Seconds $PollSeconds
 }
}catch{
 Write-StartupLog ('Startup failed: '+$_.Exception.GetType().Name+'. Inspect installation paths and configuration; scheduled task will retry.')
 throw
}finally{
 if($owned){$mutex.ReleaseMutex()}
 $mutex.Dispose()
}
