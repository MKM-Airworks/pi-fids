param(
    [ValidateSet('SHI', 'ROR')][string]$Airport = 'SHI',
    [ValidatePattern('^[A-Za-z0-9_-]{1,40}$')][string]$DisplayId = 'counter-01',
    [ValidateRange(1024, 65535)][int]$Port = 8800
)

$ErrorActionPreference = 'Stop'
# Supports machine-wide and per-user Edge locations on x86 and x64 Windows.
$candidates = @(
    (Join-Path $env:ProgramFiles 'Microsoft\Edge\Application\msedge.exe'),
    (Join-Path $env:LOCALAPPDATA 'Microsoft\Edge\Application\msedge.exe')
)
if (${env:ProgramFiles(x86)}) {
    $candidates += Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe'
}
$edge = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $edge) { throw 'Microsoft Edge was not found. Install Edge before starting Pi-FIDS.' }

# A local receiver must be started independently before this launcher.
$url = "http://127.0.0.1:$Port/display?airport=$Airport&displayId=$DisplayId&kiosk=1"
Start-Process -FilePath $edge -ArgumentList @('--kiosk', $url, '--edge-kiosk-type=fullscreen', '--no-first-run')
