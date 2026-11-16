# Pi-FIDS V2 Ubuntu installation

The manager and receiver use the same application and feed as Windows.
Build the four matching kits with the official Windows x64 embeddable Python ZIP
and a Python build environment with tzdata installed.

```sh
python3 v2/deploy/build-packages.py --windows-runtime /path/to/python-embed-amd64.zip --output ./dist --version v2-20261116.1
```

Install each role using its included bilingual START-HERE.html. Both manager
kits ship both display kits. Port 8800 is management-local, port 8805 is the
airport LAN feed and download page, and port 8801 is display-local.
If a host firewall is enabled, allow TCP 8805 from the display subnet only.
Ubuntu Desktop kiosk starts when the designated user signs in.
