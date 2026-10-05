param([Parameter(Mandatory=$true)][string]$ConfigPath)
$ErrorActionPreference='Stop'
$config=Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
$listener=New-Object System.Net.HttpListener
$listener.Prefixes.Add([string]$config.baseUrl + '/')
$listener.Start()
function ClockStatus {
  $service=Get-Service W32Time
  $source=(& w32tm.exe /query /source 2>&1 | Out-String).Trim()
  return @{utcNow=[DateTimeOffset]::UtcNow.ToString('o'); serviceStatus=[string]$service.Status; source=$source; ntpServerEnabled=[bool](Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\TimeProviders\NtpServer').Enabled}
}
while($listener.IsListening){
  $context=$listener.GetContext();$status=200;$result=@{}
  try{
    $request=$context.Request
    if(-not [Net.IPAddress]::IsLoopback($request.RemoteEndPoint.Address)){throw 'Loopback required'}
    if($request.Headers['Origin']){throw 'Direct browser access is forbidden'}
    if($request.Headers['Authorization'] -cne ('Bearer '+$config.token)){$status=401;throw 'Unauthorized'}
    if($request.HttpMethod -eq 'GET' -and $request.Url.AbsolutePath -eq '/status'){$result=ClockStatus}
    elseif($request.HttpMethod -eq 'POST' -and $request.Url.AbsolutePath -eq '/set'){
      if($request.ContentLength64 -lt 1 -or $request.ContentLength64 -gt 4096 -or $request.ContentType -notlike 'application/json*'){$status=400;throw 'Invalid request'}
      $reader=New-Object IO.StreamReader($request.InputStream)
      try{$data=$reader.ReadToEnd() | ConvertFrom-Json}finally{$reader.Dispose()}
      $target=[DateTimeOffset]::MinValue
      if(-not [DateTimeOffset]::TryParse([string]$data.utcNow,[Globalization.CultureInfo]::InvariantCulture,[Globalization.DateTimeStyles]::RoundtripKind,[ref]$target) -or $target.Offset -ne [TimeSpan]::Zero){$status=400;throw 'Invalid UTC time'}
      Set-Date -Date $target.LocalDateTime | Out-Null
      $result=ClockStatus
    }else{$status=404;throw 'Not found'}
  }catch{
    if($status -eq 200){$status=503}
    $result=@{error='Clock operation failed';code=$status}
  }
  $bytes=[Text.Encoding]::UTF8.GetBytes(($result | ConvertTo-Json -Compress))
  $context.Response.StatusCode=$status;$context.Response.ContentType='application/json; charset=utf-8'
  $context.Response.ContentLength64=$bytes.Length
  $context.Response.OutputStream.Write($bytes,0,$bytes.Length);$context.Response.Close()
}
