$ErrorActionPreference='Stop'
$root=Join-Path $env:LOCALAPPDATA 'MKM\PiFidsDisplay'
$config=Get-Content "$root\data\connection.json" -Raw | ConvertFrom-Json
$candidates=@("$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe","$env:LOCALAPPDATA\Microsoft\Edge\Application\msedge.exe")
if(${env:ProgramFiles(x86)}){$candidates+="${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"}
$edge=$candidates | Where-Object {Test-Path $_} | Select-Object -First 1
if(-not $edge){throw 'Microsoft Edge is required'}
for($i=0;$i -lt 180;$i++){
 $client=New-Object Net.Sockets.TcpClient
 try{$pending=$client.BeginConnect('127.0.0.1',8801,$null,$null);if($pending.AsyncWaitHandle.WaitOne(2000)){$client.EndConnect($pending);break}}catch{}finally{$client.Close()}
 Start-Sleep -Seconds 2
}
if($i -eq 180){throw 'Receiver did not start; inspect receiver-error.log'}
$url="http://127.0.0.1:8801/display?airport=$($config.airport)&displayId=$($config.displayId)&kiosk=1"
Start-Process $edge -ArgumentList @('--kiosk',('"'+$url+'"'),'--edge-kiosk-type=fullscreen','--no-first-run',('--user-data-dir="'+$root+'\edge-kiosk"'))
Start-Sleep -Seconds 8
& "$root\Hide-Taskbar.ps1"
