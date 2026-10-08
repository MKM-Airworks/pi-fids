$root=Join-Path $env:LOCALAPPDATA 'MKM\PiFidsManager'
$shell=New-Object -ComObject WScript.Shell
$link=$shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Pi-FIDS Add Display.lnk'))
$link.TargetPath="$root\PiFidsSetup.exe";$link.Arguments='/register';$link.Save()
