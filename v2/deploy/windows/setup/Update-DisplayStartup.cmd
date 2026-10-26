@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Update-DisplayStartup.ps1" %*
if errorlevel 1 (
 echo Update failed. Keep the error text for support.
 pause
 exit /b 1
)
echo Startup update completed. Check display-startup.log and verify the screen.
pause
