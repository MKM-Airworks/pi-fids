param([string]$Root='', [switch]$CheckOnly)
$ErrorActionPreference='Stop'
if(-not $Root){
 $roots=@('MKM\PiFidsDisplay','MKM\PiFidsV2-Test') | ForEach-Object {Join-Path $env:LOCALAPPDATA $_} | Where-Object {Test-Path (Join-Path $_ 'data\connection.json')}
 if(@($roots).Count -ne 1){throw 'Specify -Root for the existing display installation.'}
 $Root=@($roots)[0]
}
$Root=[IO.Path]::GetFullPath($Root)
if(-not(Test-Path (Join-Path $Root 'data\connection.json'))){throw 'Existing display connection.json was not found'}
$legacy=(Split-Path $Root -Leaf) -eq 'PiFidsV2-Test'
$name=if($legacy){'MKM-PiFidsV2-LogonScreen'}else{'MKM-PiFidsDisplay-Screen'}
$task=Get-ScheduledTask -TaskName $name
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$taskUser=$task.Principal.UserId
if($taskUser -ne $identity.User.Value -and $taskUser -ne $identity.Name){
 try{$sid=(New-Object Security.Principal.NTAccount($taskUser)).Translate([Security.Principal.SecurityIdentifier]).Value}catch{throw 'Cannot resolve display task user'}
 if($sid -ne $identity.User.Value){throw 'Run the update using the existing display installation account.'}
}
foreach($file in @('Open-Display.ps1','Hide-Taskbar.ps1')){
 $path=Join-Path $PSScriptRoot $file
 if(-not(Test-Path $path)){throw "Update package is incomplete: $file"}
 $tokens=$null;$errors=$null
 [Management.Automation.Language.Parser]::ParseFile($path,[ref]$tokens,[ref]$errors) | Out-Null
 if($errors.Count){throw "PowerShell parser rejected $file"}
}
if($CheckOnly){Write-Output 'Existing installation, account and startup scripts verified.';exit 0}
$backup=Join-Path $Root ('startup-backup-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backup -ErrorAction Stop | Out-Null
$xml=Export-ScheduledTask -TaskName $name
$xml | Set-Content (Join-Path $backup 'screen-task.xml') -Encoding Unicode
$present=@{}
foreach($file in @('Open-Display.ps1','Hide-Taskbar.ps1')){
 $present[$file]=Test-Path (Join-Path $Root $file)
 if($present[$file]){Copy-Item (Join-Path $Root $file) $backup -Force}
}
$wasRunning=$task.State -eq 'Running'
try{
 if($wasRunning){Stop-ScheduledTask -TaskName $name}
 foreach($file in @('Open-Display.ps1','Hide-Taskbar.ps1')){Copy-Item (Join-Path $PSScriptRoot $file) (Join-Path $Root $file) -Force}
 $profile=Join-Path $Root 'edge-kiosk'
 if($legacy -and (Test-Path (Join-Path $Root 'edge-kiosk-recovered'))){$profile=Join-Path $Root 'edge-kiosk-recovered'}
 $action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "'+$Root+'\Open-Display.ps1" -ProfileDirectory "'+$profile+'"')
 # Preserve account, logon trigger and battery settings. Remove only the
 # elapsed-time cutoff and enable retry after an actual worker failure.
 $settings=$task.Settings
 $settings.ExecutionTimeLimit='PT0S'
 $settings.RestartCount=3
 $settings.RestartInterval='PT1M'
 $settings.MultipleInstances='IgnoreNew'
 Set-ScheduledTask -TaskName $name -Action $action -Settings $settings | Out-Null
 Start-ScheduledTask -TaskName $name
 Write-Output "Startup updated. Backup: $backup"
}catch{
 $failure=$_
 Stop-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
 foreach($file in @('Open-Display.ps1','Hide-Taskbar.ps1')){
  if($present[$file]){Copy-Item (Join-Path $backup $file) (Join-Path $Root $file) -Force}
  else{Remove-Item (Join-Path $Root $file) -ErrorAction SilentlyContinue}
 }
 Register-ScheduledTask -TaskName $name -Xml $xml -Force | Out-Null
 if($wasRunning){Start-ScheduledTask -TaskName $name}
 throw $failure
}
