$ErrorActionPreference='Stop'
for($i=0;$i -lt 180;$i++){
 try{$r=Invoke-WebRequest 'http://127.0.0.1:8800/' -UseBasicParsing -TimeoutSec 2;if($r.StatusCode -eq 200){Start-Process 'http://127.0.0.1:8800/';exit 0}}catch{}
 Start-Sleep -Seconds 2
}
throw 'Manager did not start. Inspect manager-error.log.'
