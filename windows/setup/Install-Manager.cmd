@echo off
set /p siteAirport=Airport code (example SHI): 
set /p siteTimezone=IANA time zone (example Asia/Tokyo): 
set /p siteLan=This management PC LAN IPv4: 
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-Manager.ps1" -Airport "%siteAirport%" -Timezone "%siteTimezone%" -LanAddress "%siteLan%"
pause
