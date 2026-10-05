# Run once from an elevated Windows PowerShell prompt on the management PC.
[CmdletBinding(SupportsShouldProcess=$true)]
param([Parameter(Mandatory=$true)][string]$OperatorAccount,[int]$ClockPort=8816,[string]$AllowedSubnet='LocalSubnet')
$ErrorActionPreference='Stop'
$principal=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Run as Administrator'}
if($ClockPort -lt 1024 -or $ClockPort -gt 65535){throw 'Invalid helper port'}
if((Get-CimInstance Win32_ComputerSystem).PartOfDomain){throw 'Domain-managed clocks require the domain time administrator configuration'}
$identity=New-Object Security.Principal.NTAccount($OperatorAccount)
$sid=$identity.Translate([Security.Principal.SecurityIdentifier])
$root=Join-Path $env:ProgramData 'PiFIDS-Clock'
if(-not $PSCmdlet.ShouldProcess($env:COMPUTERNAME,'Configure offline LAN NTP server and install the restricted clock helper')){return}
if((Test-Path -LiteralPath $root) -and ((Get-Item -LiteralPath $root).Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Clock service directory must not be a reparse point'}
New-Item -ItemType Directory -Path $root -Force | Out-Null
foreach($item in (Get-ChildItem -LiteralPath $root -Force)){if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Clock service files must not be reparse points'}}
# Protect the helper before copying executable code into the SYSTEM task folder.
$acl=New-Object Security.AccessControl.DirectorySecurity
$acl.SetAccessRuleProtection($true,$false)
foreach($entry in @(@('S-1-5-18','FullControl'),@('S-1-5-32-544','FullControl'),@($sid.Value,'ReadAndExecute'))){
  $entrySid=[Security.Principal.SecurityIdentifier]::new([string]$entry[0])
  $rights=[Security.AccessControl.FileSystemRights]([Enum]::Parse([Security.AccessControl.FileSystemRights],[string]$entry[1]))
  $rule=[Security.AccessControl.FileSystemAccessRule]::new($entrySid,$rights,[Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit',[Security.AccessControl.PropagationFlags]::None,[Security.AccessControl.AccessControlType]::Allow)
  $acl.AddAccessRule($rule)
}
Set-Acl -LiteralPath $root -AclObject $acl
$helper=Join-Path $root 'Clock-Service.ps1';Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Clock-Service.ps1') -Destination $helper -Force
$configPath=Join-Path $root 'connection.json'
if(-not (Test-Path -LiteralPath $configPath)){
  $random=New-Object byte[] 32;$rng=[Security.Cryptography.RandomNumberGenerator]::Create();try{$rng.GetBytes($random)}finally{$rng.Dispose()}
  @{baseUrl="http://127.0.0.1:$ClockPort";token=[Convert]::ToBase64String($random)} | ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding UTF8
}else{
  $existing=Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
  if($existing.baseUrl -ne "http://127.0.0.1:$ClockPort"){throw 'Existing helper uses a different port'}
}
Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\Parameters' -Name Type -Value 'NoSync'
Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\TimeProviders\NtpServer' -Name Enabled -Value 1
Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\Config' -Name AnnounceFlags -Value 5
Set-Service W32Time -StartupType Automatic;Restart-Service W32Time
if(-not (Get-NetFirewallRule -Name 'PiFIDS-LAN-NTP' -ErrorAction SilentlyContinue)){
  New-NetFirewallRule -Name 'PiFIDS-LAN-NTP' -DisplayName 'Pi-FIDS LAN time server' -Direction Inbound -Protocol UDP -LocalPort 123 -RemoteAddress $AllowedSubnet -Action Allow -Profile Private,Domain | Out-Null
}
$fileAcl=[Security.AccessControl.FileSecurity]::new()
$fileAcl.SetAccessRuleProtection($true,$false)
foreach($entry in @(@('S-1-5-18','FullControl'),@('S-1-5-32-544','FullControl'),@($sid.Value,'ReadAndExecute'))){
  $fileAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new([string]$entry[0]),[Security.AccessControl.FileSystemRights]([Enum]::Parse([Security.AccessControl.FileSystemRights],[string]$entry[1])),[Security.AccessControl.AccessControlType]::Allow))
}
Set-Acl -LiteralPath $helper -AclObject $fileAcl
Set-Acl -LiteralPath $configPath -AclObject $fileAcl
$powershell=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$action=New-ScheduledTaskAction -Execute $powershell -Argument ('-NoProfile -ExecutionPolicy Bypass -File "'+$helper+'" -ConfigPath "'+$configPath+'"')
$trigger=New-ScheduledTaskTrigger -AtStartup
$settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName 'PiFIDS-Clock-Service' -Action $action -Trigger $trigger -Settings $settings -User 'SYSTEM' -RunLevel Highest -Force | Out-Null
Start-ScheduledTask -TaskName 'PiFIDS-Clock-Service'
Write-Output ('Clock helper installed. Start the FIDS manager with --clock-service "'+$configPath+'"')
