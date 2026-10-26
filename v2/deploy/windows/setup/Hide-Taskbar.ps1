if(-not ('FidsShell' -as [type])){Add-Type @'
using System;
using System.Runtime.InteropServices;
public class FidsShell {
 [StructLayout(LayoutKind.Sequential)] public struct RECT {public int left,top,right,bottom;}
 [StructLayout(LayoutKind.Sequential)] public struct APPBARDATA {public uint cbSize;public IntPtr hWnd;public uint uCallbackMessage,uEdge;public RECT rc;public IntPtr lParam;}
 [DllImport("shell32.dll")] public static extern UIntPtr SHAppBarMessage(uint m,ref APPBARDATA d);
 [DllImport("user32.dll",CharSet=CharSet.Auto)] public static extern IntPtr FindWindow(string c,string n);
}
'@
}
$d=New-Object FidsShell+APPBARDATA
$d.cbSize=[Runtime.InteropServices.Marshal]::SizeOf($d)
$d.hWnd=[FidsShell]::FindWindow('Shell_TrayWnd',$null)
$before=[FidsShell]::SHAppBarMessage(4,[ref]$d).ToUInt64()
$r=$PSScriptRoot
if($d.hWnd -eq [IntPtr]::Zero){throw 'Windows taskbar is not ready'}
if(-not(Test-Path "$r\data\taskbar-before.txt")){$before | Set-Content "$r\data\taskbar-before.txt"}
$d.lParam=[IntPtr]1
[FidsShell]::SHAppBarMessage(10,[ref]$d) | Out-Null
$p=Get-CimInstance Win32_Process -Filter "name='msedge.exe'" | Where-Object {$_.CommandLine -like '*--kiosk*' -and $_.CommandLine -like '*PiFidsDisplay\edge-kiosk*'} | Select-Object -First 1
if($p){$w=New-Object -ComObject WScript.Shell;$w.AppActivate([int]$p.ProcessId) | Out-Null}
