param([string]$Root=(Join-Path $env:LOCALAPPDATA 'MKM\PiFidsV2-Test'),[string]$Source='http://192.168.11.20:8805')
$ErrorActionPreference='Stop'
$airport=Read-Host 'Airport (SHI / ROR)'
$id=Read-Host 'Terminal ID (example: counter-02)'
if($airport -notin @('SHI','ROR') -or $id -notmatch '^[A-Za-z0-9_-]{1,40}$'){throw 'Invalid airport or terminal ID'}
$name=Read-Host 'Terminal name'
$choice=Read-Host 'Display: 1=departures, 2=arrivals, 3=counter/gate image'
if($choice -notin @('1','2','3')){throw 'Select 1, 2 or 3'}
$registry=Invoke-RestMethod "http://127.0.0.1:8800/api/registry?airport=$airport"
if($registry.terminals | Where-Object {$_.displayId -eq $id -or $_.name -eq $name}){throw 'Terminal ID or name already exists. Use management settings to edit it.'}
$profile=$null
if($choice -eq '3'){
 $profiles=@($registry.profiles)
 if(-not $profiles.Count){throw 'Register an image layout in management first'}
 for($i=0;$i -lt $profiles.Count;$i++){Write-Host ($i.ToString()+': '+$profiles[$i].name)}
 $selected=Read-Host 'Select layout number'
 if($selected -notmatch '^\d+$' -or [int]$selected -ge $profiles.Count){throw 'Invalid layout number'}
 $profile=$profiles[[int]$selected].name
}
$auth=Join-Path $Root 'data\lan-auth.json'
$config=Get-Content $auth -Raw | ConvertFrom-Json
if($config.airport -ne $airport){throw 'LAN service airport differs. Configure the matching airport feed first.'}
$folder=Join-Path $Root 'data\enrollment'
New-Item -ItemType Directory -Path $folder -Force | Out-Null
$user=[Security.Principal.WindowsIdentity]::GetCurrent().Name
& icacls.exe $folder /inheritance:r /grant:r "${user}:(OI)(CI)F" '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F' | Out-Null
if($LASTEXITCODE -ne 0){throw 'Could not protect connection folder'}
$output=Join-Path $folder "$id.connection.json"
if(Test-Path $output){throw 'Connection file already exists'}
$body=@{airport=$airport;displayId=$id;name=$name;usage=$(if($choice -eq '3'){'signage'}else{'board'});board=@{direction=$(if($choice -eq '2'){'arrival'}else{'departure'})}}
Invoke-RestMethod 'http://127.0.0.1:8800/api/terminals' -Method Post -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes(($body | ConvertTo-Json -Depth 5))) | Out-Null
if($profile){Invoke-RestMethod 'http://127.0.0.1:8800/api/signage' -Method Post -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes((@{airport=$airport;displayId=$id;profileName=$profile}|ConvertTo-Json))) | Out-Null}
Push-Location "$Root\v2"
try{& "$Root\runtime\python.exe" -m pifids.security terminal --config $auth --display-id $id --source $Source --output $output;if($LASTEXITCODE -ne 0){throw 'Connection issuance failed; remove incomplete registration in management.'}}finally{Pop-Location}
Write-Host "Prepared: $name ($id)"
Write-Host "Copy ONLY this connection file to the new display PC: $output"
