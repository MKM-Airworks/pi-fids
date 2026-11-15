param([string]$Root,[string]$Source,[string]$Airport,[string]$DisplayId,[string]$TerminalName,[ValidateSet('departure','arrival','signage')][string]$Usage,[string]$ProfileName)
if(-not $Root){$Root=Join-Path $env:LOCALAPPDATA 'MKM\PiFidsManager';if(-not(Test-Path "$Root\data\site.json")){$Root=Join-Path $env:LOCALAPPDATA 'MKM\PiFidsV2-Test'}}
if(-not $Source){if(Test-Path "$Root\data\site.json"){$site=Get-Content "$Root\data\site.json" -Raw | ConvertFrom-Json;$Source='http://'+$site.lanAddress+':8805'}else{$Source='http://192.168.11.20:8805'}}
$ErrorActionPreference='Stop'
if(-not $Airport){$Airport=Read-Host 'Airport (3-letter code)'}
$airport=$Airport
$id=$DisplayId;if(-not $id){$id=Read-Host 'Terminal ID (example: counter-02)'}
if($airport -notmatch '^[A-Z]{3}$' -or $id -notmatch '^[A-Za-z0-9_-]{1,40}$'){throw 'Invalid airport or terminal ID'}
$name=$TerminalName;if(-not $name){$name=Read-Host 'Terminal name'}
$choice=switch($Usage){'departure'{'1'} 'arrival'{'2'} 'signage'{'3'} default{Read-Host 'Display: 1=departures, 2=arrivals, 3=counter/gate image'}}
if($choice -notin @('1','2','3')){throw 'Select 1, 2 or 3'}
$status=Invoke-RestMethod 'http://127.0.0.1:8800/api/session'
if(-not $status.secured){throw 'Enable management login before registering a display.'}
if($status.setupRequired){throw 'Open management in the browser and register the initial administrator first.'}
$loginName=Read-Host 'Administrator username'
$securePassword=Read-Host 'Administrator password' -AsSecureString
$pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
try {
 $loginPassword=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
 Invoke-RestMethod 'http://127.0.0.1:8800/api/login' -Method Post -ContentType 'application/json' -Body (@{username=$loginName;password=$loginPassword}|ConvertTo-Json) -SessionVariable managerSession | Out-Null
} finally {
 [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
 $loginPassword=$null
 $securePassword.Dispose()
}
$identity=Invoke-RestMethod 'http://127.0.0.1:8800/api/session' -WebSession $managerSession
if($identity.user.role -ne 'admin'){throw 'Administrator role is required for terminal registration.'}
$registry=Invoke-RestMethod "http://127.0.0.1:8800/api/registry?airport=$airport" -WebSession $managerSession
if($registry.terminals | Where-Object {$_.displayId -eq $id -or $_.name -eq $name}){throw 'Terminal ID or name already exists. Use management settings to edit it.'}
$profile=$null
if($choice -eq '3'){
 $profiles=@($registry.profiles)
 if(-not $profiles.Count){throw 'Register an image layout in management first'}
 for($i=0;$i -lt $profiles.Count;$i++){Write-Host ($i.ToString()+': '+$profiles[$i].name)}
 if($ProfileName){$selected=[Array]::IndexOf(@($profiles | ForEach-Object {$_.name}),$ProfileName).ToString()}else{$selected=Read-Host 'Select layout number'}
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
Invoke-RestMethod 'http://127.0.0.1:8800/api/terminals' -Method Post -WebSession $managerSession -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes(($body | ConvertTo-Json -Depth 5))) | Out-Null
if($profile){Invoke-RestMethod 'http://127.0.0.1:8800/api/signage' -Method Post -WebSession $managerSession -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes((@{airport=$airport;displayId=$id;profileName=$profile}|ConvertTo-Json))) | Out-Null}
Push-Location "$Root\v2"
try{& "$Root\runtime\python.exe" -m pifids.security terminal --config $auth --display-id $id --source $Source --output $output;if($LASTEXITCODE -ne 0){throw 'Connection issuance failed; remove incomplete registration in management.'}}finally{Pop-Location}
Write-Host "Prepared: $name ($id)"
Write-Host "Copy ONLY this connection file to the new display PC: $output"

Invoke-RestMethod 'http://127.0.0.1:8800/api/logout' -Method Post -ContentType 'application/json' -Body '{}' -WebSession $managerSession | Out-Null
