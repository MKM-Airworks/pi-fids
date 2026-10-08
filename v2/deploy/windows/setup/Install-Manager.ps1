param([Parameter(Mandatory=$true)][string]$Airport,[Parameter(Mandatory=$true)][string]$Timezone,[Parameter(Mandatory=$true)][string]$LanAddress,[switch]$CheckOnly)
$ErrorActionPreference='Stop'
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=New-Object Security.Principal.WindowsPrincipal($identity)
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Run setup as administrator using the management account.'}
$ip=$null
if(-not [Net.IPAddress]::TryParse($LanAddress,[ref]$ip) -or $ip.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork -or $ip.ToString() -eq '0.0.0.0' -or [Net.IPAddress]::IsLoopback($ip)){throw 'Select this management PC LAN IPv4 address'}
if(-not(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -eq $LanAddress})){throw 'The LAN address does not belong to this PC'}
$network=Get-NetConnectionProfile | Where-Object {$_.InterfaceIndex -in @(Get-NetIPAddress -IPAddress $LanAddress).InterfaceIndex}
if(-not($network | Where-Object {$_.NetworkCategory -in @('Private','DomainAuthenticated')})){throw 'Set this trusted airport LAN to Private before setup.'}
$root=Join-Path $env:LOCALAPPDATA 'MKM\PiFidsManager'
& "$PSScriptRoot\runtime\python.exe" "$PSScriptRoot\Initialize-Manager.py" --root $root --airport $Airport --timezone $Timezone --lan-address $LanAddress --check-only
if($LASTEXITCODE -ne 0){throw 'Airport or timezone is invalid'}
if($CheckOnly){exit 0}
if(Test-Path "$root\data\site.json"){throw 'Manager is already installed. Existing airport and data are preserved.'}
foreach($port in @(8800,8805)){if(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue){throw "Port $port is occupied. Existing management service is preserved."}}
foreach($name in @('MKM-PiFidsManager-Service','MKM-PiFidsManager-Screen')){if(Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue){throw "Task already exists: $name"}}
New-Item -ItemType Directory -Path "$root\data" -Force | Out-Null
$user=$identity.Name
& icacls.exe "$root\data" /inheritance:r /grant:r "${user}:(OI)(CI)F" '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F' | Out-Null
if($LASTEXITCODE -ne 0){throw 'Could not protect management settings'}
Copy-Item "$PSScriptRoot\runtime","$PSScriptRoot\v2" $root -Recurse -Force
Copy-Item "$PSScriptRoot\Run-Manager.pyw","$PSScriptRoot\Open-Manager.ps1","$PSScriptRoot\Prepare-Display.ps1","$PSScriptRoot\Prepare-Display.cmd" $root -Force
& "$PSScriptRoot\runtime\python.exe" "$PSScriptRoot\Initialize-Manager.py" --root $root --airport $Airport --timezone $Timezone --lan-address $LanAddress
if($LASTEXITCODE -ne 0){throw 'Could not initialize management data'}
& reg.exe export 'HKLM\SYSTEM\CurrentControlSet\Services\W32Time' "$root\data\time-before.reg" /y | Out-Null
if($LASTEXITCODE -ne 0){throw 'Could not back up Windows Time'}
Get-CimInstance Win32_Service -Filter "Name='W32Time'" | Select-Object StartMode,State | ConvertTo-Json | Set-Content "$root\data\time-service-before.json"
Set-Service W32Time -StartupType Automatic
Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\Parameters' Type 'NoSync'
Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\TimeProviders\NtpServer' Enabled 1
Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\Config' AnnounceFlags 5
Restart-Service W32Time
New-NetFirewallRule -Name 'MKM-PiFidsManager-Feed' -DisplayName 'Pi-FIDS display feed' -Direction Inbound -Action Allow -Protocol TCP -LocalAddress $LanAddress -LocalPort 8805 -RemoteAddress LocalSubnet -Profile Private,Domain | Out-Null
New-NetFirewallRule -Name 'MKM-PiFidsManager-NTP' -DisplayName 'Pi-FIDS time server' -Direction Inbound -Action Allow -Protocol UDP -LocalAddress $LanAddress -LocalPort 123 -RemoteAddress LocalSubnet -Profile Private,Domain | Out-Null
$profiles=Get-NetConnectionProfile | Where-Object {$_.InterfaceIndex -in @(Get-NetIPAddress -IPAddress $LanAddress).InterfaceIndex}
if($profiles.NetworkCategory -contains 'Public'){Write-Warning 'LAN is Public. Set the trusted airport LAN to Private before connecting displays.'}
$taskPrincipal=New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$trigger=New-ScheduledTaskTrigger -AtLogOn -User $user
Register-ScheduledTask -TaskName 'MKM-PiFidsManager-Service' -Action (New-ScheduledTaskAction -Execute "$root\runtime\pythonw.exe" -Argument ('"'+$root+'\Run-Manager.pyw"') -WorkingDirectory "$root\v2") -Trigger $trigger -Principal $taskPrincipal -Settings $settings | Out-Null
Register-ScheduledTask -TaskName 'MKM-PiFidsManager-Screen' -Action (New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "'+$root+'\Open-Manager.ps1"')) -Trigger $trigger -Principal $taskPrincipal -Settings $settings | Out-Null
$shell=New-Object -ComObject WScript.Shell
foreach($entry in @(@('Pi-FIDS Management','Open-Manager.ps1'),@('Pi-FIDS Add Display','Prepare-Display.ps1'))){
 $link=$shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) ($entry[0]+'.lnk')))
 $link.TargetPath='powershell.exe';$link.Arguments='-NoProfile -ExecutionPolicy Bypass -File "'+$root+'\'+$entry[1]+'"';$link.Save()
}
Start-ScheduledTask -TaskName 'MKM-PiFidsManager-Service'
Start-ScheduledTask -TaskName 'MKM-PiFidsManager-Screen'
Write-Host 'Management setup complete. Verify LAN, time and terminal registration before installation acceptance.'
