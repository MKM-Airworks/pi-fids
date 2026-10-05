[CmdletBinding(SupportsShouldProcess=$true)]
param([Parameter(Mandatory=$true)][string]$TimeServer)
$ErrorActionPreference='Stop'
if($TimeServer -notmatch '^[A-Za-z0-9][A-Za-z0-9.-]{0,252}$'){throw 'Enter a management PC IPv4 address or hostname'}
$principal=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Run as Administrator'}
if((Get-CimInstance Win32_ComputerSystem).PartOfDomain){throw 'Configure domain time synchronization through the domain administrator'}
if(-not $PSCmdlet.ShouldProcess($env:COMPUTERNAME,"Synchronize OS time with LAN management PC $TimeServer")){return}
Set-Service W32Time -StartupType Automatic;Start-Service W32Time
& w32tm.exe /config "/manualpeerlist:$TimeServer,0x8" /syncfromflags:manual /update
if($LASTEXITCODE -ne 0){throw 'Time service configuration failed'}
Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\Config' -Name MinPollInterval -Value 6
Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\Config' -Name MaxPollInterval -Value 6
Restart-Service W32Time
& w32tm.exe /resync /rediscover
if($LASTEXITCODE -ne 0){throw 'No time data available. Check management PC NTP service and UDP 123 connectivity'}
& w32tm.exe /query /status
