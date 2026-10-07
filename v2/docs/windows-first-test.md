# First Windows test — 2026-10-07

Windows 11 Pro x64, Python 3.13.16 embeddable x64, Microsoft Edge.
The official Python archive SHA-256 was verified before deployment.

The test environment is isolated in `%LOCALAPPDATA%\MKM\PiFidsV2-Test`.
The manager listens on localhost port 8800; three local receivers use 8801
(SHI departures), 8802 (SHI arrivals), and 8803 (SHI counter-01).
Each receiver has a separate persistent SQLite database. No LAN feed or
MKM Flight Web connection is enabled. Manager authentication is not configured
for this localhost-only test. OS clock/NTP configuration was not changed.

SHI and ROR each have six clearly labelled TEST flights, plus named departure,
arrival and counter terminals. The counter profile is text-only until artwork
is registered. Test flights follow the ordinary display expiry settings.

Desktop shortcuts open management, departures, arrivals, check-in and Edge
Kiosk. Start Test and Stop Test control the `MKM-PiFidsV2-Test` scheduled task.
The task is started manually; automatic startup after reboot is not configured.
`MKM-PiFidsV2-OpenPreview` launches the normal preview browser interactively.
Preview and Kiosk use separate browser profile directories.

## Evidence and limits

- 39 Python tests passed on Windows, including LAN authentication/receiver,
  persistent storage, upstream conversion and OS clock helper client tests.
- All four local services returned HTTP 200; receiver feeds contained the
  expected departure, arrival and counter controls.
- Existing Windows PowerShell scripts parsed successfully.
- Initial Windows tests exposed unclosed SQLite connections. Store connections
  now commit or roll back and close when leaving their context. A regression
  test verifies success and failure paths. The legacy migration fixture also
  closes its manually opened connection.
- Browser appearance, actual Edge Kiosk operation, real image upload,
  cross-PC LAN operation, OS time synchronization and Windows 10 x86 remain
  separate validation steps. Passing helper client tests does not confirm
  privileged Windows clock operation.

The existing V1 code and MKM Flight Web were not changed by this deployment.

## LAN time server follow-up

The management PC was configured as an offline authoritative Windows Time
server (Type=NoSync, NtpServer Enabled=1, AnnounceFlags=5). Its original Type,
server flag, announcement flag and service start type were backed up to
`data/w32time-before-fids.json`. The OS time value was not manually changed.
UDP 123 is allowed for Private-profile LocalSubnet traffic by PiFIDS-LAN-NTP.
An NTP request from the Mac received a matching server response, stratum 1,
with a 53ms round trip. The observed difference from the Mac clock was about
4 seconds; this validates LAN response, not absolute clock accuracy.

On Windows, the manager now reads W32Time service and NTP provider status
without administrator privileges. This read-only path cannot change the OS
clock; manual correction still requires manager authentication and the
privileged clock helper. Actual client OS following remains to be verified on
a separate Windows/Pi device. Both Windows and Mac passed 40 Python tests.
