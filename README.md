# Pi-FIDS V2 — ROR Render demo

Separate Linux demo only. Do not deploy this as a Windows update, reuse production credentials, or point production displays at it. Uses the Pi-FIDS V2 application from Windows branch develop/v2 at b01ef1c, with a demo-specific entry point and controls. The default demo arrivals board shows baggage belt instead of gate. No Windows installation files are included.

Create a separate Render Blueprint from this directory as the repository root. It requests a paid single-instance Python web service and a dedicated persistent disk. Set DEMO_ORIGIN to the final HTTPS service origin; set a demo-admin password of at least 12 characters and a distinct random URL-safe display token (32–128 characters). Configure ROR_FDD_ORIGIN and the ROR organization/airport UUIDs. Set ROR_FDD_TOKEN to a separately issued, ROR-only, pi-fids read-only token. Enter secrets in Render; do not commit them. Production schedules are fetched read-only; preview releases are rejected.

Sign in as demo-admin. In the flight management screen select an operating date in the published ROR schedule and use check → import → publish. Open /demo to switch between Departures, Check-in and Gate. The two included images are test artwork. The demo opens on an empty departures board until data is published.

For a demo display PC, use the existing HTTPS receiver with a locally created private connection.json containing source (DEMO_ORIGIN), airport (ROR), timezone (Pacific/Palau), displayId (ror-demo) and token (DEMO_DISPLAY_TOKEN). Use a distinct receiver database and browser profile; the receiver listens on localhost and Edge Kiosk opens its local /display?airport=ROR&displayId=ror-demo&kiosk=1. Never transfer ROR_FDD_TOKEN to the display PC.

Render readiness endpoint: /healthz. Writes require a matching HTTPS Origin and an authenticated manager, except login. Setup, Windows clock changes and automatic upstream mode are disabled. The terminal token only grants the published feed and its referenced assets. Keep this service and its credentials separate from the Windows deployment.
