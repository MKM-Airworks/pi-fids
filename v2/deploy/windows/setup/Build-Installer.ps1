param([Parameter(Mandatory=$true)][string]$Payload,[string]$Output=(Join-Path $PSScriptRoot 'PiFids-Setup-Windows-x64.exe'),[switch]$CompileOnly)
$ErrorActionPreference='Stop'
$csc=Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if(-not(Test-Path $csc)){throw '.NET Framework compiler not found'}
& $csc /nologo /target:winexe /platform:x64 /codepage:65001 /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Web.Extensions.dll "/win32manifest:$PSScriptRoot\installer.manifest" "/resource:$Payload,payload.zip" "/out:$Output" "$PSScriptRoot\Installer.cs" "$PSScriptRoot\Enrollment.cs"
if($LASTEXITCODE -ne 0){throw 'Installer compilation failed'}
if(-not $CompileOnly){
 & $Output /verify
 if($LASTEXITCODE -ne 0){throw 'Installer payload verification failed'}
}
Get-FileHash $Output -Algorithm SHA256 | Select-Object Hash,Path
