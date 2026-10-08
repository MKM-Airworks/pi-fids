param([string]$ConnectionFile,[switch]$CheckOnly)
$ErrorActionPreference='Stop'
$principal=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Run setup as administrator using the account that will display Pi-FIDS.'}
if(-not $ConnectionFile){$ConnectionFile=Read-Host 'Path to terminal connection JSON'}
$ConnectionFile=$ConnectionFile.Trim('"')
$config=Get-Content -LiteralPath $ConnectionFile -Raw | ConvertFrom-Json
if($config.airport -notin @('SHI','ROR') -or $config.displayId -notmatch '^[A-Za-z0-9_-]{1,40}$' -or $config.token -notmatch '^[A-Za-z0-9_-]{32,128}$'){throw 'Invalid connection file'}
$source=[Uri]$config.source
if($source.Scheme -notin @('http','https') -or $source.UserInfo -or $source.Query -or $source.Fragment -or $source.AbsolutePath -ne '/'){throw 'Invalid feed address'}
if(-not [Environment]::Is64BitOperatingSystem){throw 'This package requires 64-bit Windows'}
if(-not(Test-Path "$PSScriptRoot\runtime\pythonw.exe") -or -not(Test-Path "$PSScriptRoot\v2\pifids\receiver.py")){throw 'Package is incomplete'}
$candidates=@("$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe","$env:LOCALAPPDATA\Microsoft\Edge\Application\msedge.exe")
if(${env:ProgramFiles(x86)}){$candidates+="${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"}
if(-not($candidates | Where-Object {Test-Path $_})){throw 'Microsoft Edge is required'}
# Verify terminal identity before changing this PC.
$feed=Invoke-RestMethod ($config.source.TrimEnd('/')+'/api/feed?airport='+$config.airport+'&displayId='+$config.displayId) -Headers @{Authorization=('Bearer '+$config.token)} -TimeoutSec 30
if($feed.airport -ne $config.airport -or $feed.control.displayId -ne $config.displayId){throw 'Feed identity differs from connection settings'}
Write-Host "Connection verified: $($config.airport) / $($config.displayId)"
if($CheckOnly){exit 0}
foreach($name in @('MKM-PiFidsDisplay-Receiver','MKM-PiFidsDisplay-Screen')){if(Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue){throw "Task already exists: $name"}}
$root=Join-Path $env:LOCALAPPDATA 'MKM\PiFidsDisplay'
if(Test-Path "$root\data\connection.json"){throw 'Already installed. Existing terminal configuration will not be overwritten.'}
$listeners=Get-NetTCPConnection -State Listen -LocalPort 8801 -ErrorAction SilentlyContinue
if($listeners){throw 'Port 8801 is occupied. Stop the existing receiver before installing.'}
$user=[Security.Principal.WindowsIdentity]::GetCurrent().Name
New-Item -ItemType Directory -Path "$root\data" -Force | Out-Null
& icacls.exe "$root\data" /inheritance:r /grant:r "${user}:(OI)(CI)F" '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F' | Out-Null
if($LASTEXITCODE -ne 0){throw 'Could not protect local connection settings'}
Copy-Item "$PSScriptRoot\runtime","$PSScriptRoot\v2" $root -Recurse -Force
Copy-Item "$PSScriptRoot\Run-Receiver.pyw","$PSScriptRoot\Open-Display.ps1","$PSScriptRoot\Hide-Taskbar.ps1" $root -Force
Copy-Item -LiteralPath $ConnectionFile -Destination "$root\data\connection.json"
# Preserve Windows Time settings so an installer change can be undone.
& reg.exe export 'HKLM\SYSTEM\CurrentControlSet\Services\W32Time' "$root\data\time-before.reg" /y | Out-Null
if($LASTEXITCODE -ne 0){throw 'Could not back up Windows Time'}
Get-CimInstance Win32_Service -Filter "Name='W32Time'" | Select-Object StartMode,State | ConvertTo-Json | Set-Content "$root\data\time-service-before.json"
Set-Service W32Time -StartupType Automatic
Start-Service W32Time
& w32tm.exe /config "/manualpeerlist:$($source.Host),0x8" /syncfromflags:manual /update | Out-Null
if($LASTEXITCODE -ne 0){throw 'Time configuration failed'}
Restart-Service W32Time
$taskPrincipal=New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$trigger=New-ScheduledTaskTrigger -AtLogOn -User $user
$settings=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$receiver=New-ScheduledTaskAction -Execute "$root\runtime\pythonw.exe" -Argument ('"'+$root+'\Run-Receiver.pyw"') -WorkingDirectory "$root\v2"
$screen=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "'+$root+'\Open-Display.ps1"')
Register-ScheduledTask -TaskName 'MKM-PiFidsDisplay-Receiver' -Action $receiver -Trigger $trigger -Principal $taskPrincipal -Settings $settings | Out-Null
Register-ScheduledTask -TaskName 'MKM-PiFidsDisplay-Screen' -Action $screen -Trigger $trigger -Principal $taskPrincipal -Settings $settings | Out-Null
$shell=New-Object -ComObject WScript.Shell
$shortcut=$shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Pi-FIDS Display.lnk'))
$shortcut.TargetPath='powershell.exe';$shortcut.Arguments='-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "'+$root+'\Open-Display.ps1"';$shortcut.Save()
Start-ScheduledTask -TaskName 'MKM-PiFidsDisplay-Receiver'
Start-ScheduledTask -TaskName 'MKM-PiFidsDisplay-Screen'
& w32tm.exe /resync /rediscover | Out-Null
if($LASTEXITCODE -ne 0){Write-Warning 'Time sync is pending. Verify the source with w32tm /query /status.'}
Write-Host 'Setup complete. Log in with this account after restarting to verify the display.'
