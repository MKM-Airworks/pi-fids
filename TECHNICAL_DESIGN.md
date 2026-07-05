Pi-FIDS Version 1.0 Technical Design Specification
Document status: Official Version 1.0 design baseline
System: Pi-FIDS (Raspberry Pi Flight Information Display System)
Implementation baseline: Git revision 88dda4fb1c1c33ba4768cae7be2b1a13e98be0f6
Document version: 1.0
Date: 2026-07-05
1. Purpose
This document defines the technical design of Pi-FIDS Version 1.0. It records the architecture, runtime behavior, external dependencies, deployment model, installation and operating procedures, failure behavior, security posture, and intended modernization path.
The implementation baseline is authoritative when this document and the source disagree. This specification deliberately distinguishes among:
behavior implemented by Version 1.0;
operating procedures required around the implementation; and
future capabilities that are not part of Version 1.0.
This document does not authorize or describe an implementation change.
2. Scope
Pi-FIDS Version 1.0 is a single-device flight information display prototype. A Raspberry Pi reads departure or arrival data from Google Sheets, renders it as an airport-style HTML table, and displays it in a local Chromium kiosk window.
Version 1.0 includes:
departure and arrival HTTP routes;
service-account access to Google Sheets;
worksheet-to-display column mapping;
scheduled time and ETD presentation;
status color classification;
airline logo selection by flight-number prefix;
a browser-driven 30-second refresh cycle by default; and
an intended desktop autostart entry.
Version 1.0 does not include:
flight data ingestion from airline or airport systems;
a database or local durable cache;
an administration interface;
user authentication or authorization;
high-availability clustering;
automatic offline recovery;
systemd service management;
a supported container image; or
guaranteed operation on Raspberry Pi OS Bookworm.
3. Design philosophy
The Version 1.0 design prioritizes prototype simplicity, low operating cost, and ease of content administration over scalability and formal service management.
Its principal design choices are:
Use familiar tools. Flight data is maintained in a spreadsheet rather than a custom administration application.
Keep the device self-contained. The Pi hosts both the presentation server and the browser that consumes it.
Use a web presentation layer. HTML and CSS provide layout without a platform-specific GUI toolkit.
Avoid interactive authentication. A Google service account permits unattended startup.
Prefer replacement rendering to client-side state. Every refresh creates a complete page from a fresh worksheet read.
Keep configuration small. Spreadsheet identity, worksheet name, and update interval are ordinary Python constants.
Accept prototype constraints. The design has no cache, process supervisor, schema validator, or offline screen.
The repository contains no architectural decision records. The rationale in Sections 4 through 6 formalizes the tradeoffs evident in the implementation; it should not be treated as a historical record of the original author's deliberations.
4. Selection of Google Sheets
4.1 Rationale
Google Sheets provides a remotely editable data source that non-developers can operate without SSH access, a database client, or a custom management interface. It also supplies tabular storage, worksheet separation, sharing controls, revision history, and an established API.
For a prototype FIDS, this reduces implementation and operational complexity:
flight rows can be edited from a computer or mobile device;
departure and arrival data can occupy separate worksheets;
the Raspberry Pi does not need to host persistent business data;
service-account authentication supports unattended operation; and
no database schema migration or backup subsystem is required on the Pi.
4.2 Accepted tradeoffs
This choice requires continuous Internet access and makes display freshness dependent on Google availability, API quotas, valid credentials, and worksheet permissions. Spreadsheet columns are only weakly structured, so accidental header or format changes can alter the display. Version 1.0 reads the complete worksheet on every page request and does not retain the last successful response.
4.3 Authentication model
The application requires a Google service-account JSON file at:
<application directory>/service_account.json
The spreadsheet identified by SHEET_KEY must be shared with the service account's email address. The application calls gspread.service_account() without an explicit scope list. Consequently, gspread's default Google Sheets and Google Drive read/write scopes are requested, even though Pi-FIDS only reads worksheet values.
5. Selection of Flask
5.1 Rationale
Flask supplies the minimum web capabilities required by the prototype:
URL routing;
template rendering;
static-file serving;
HTTP response handling; and
a directly executable development server.
It allows the application, presentation template, and route definitions to remain in one Python file. This is appropriate for the small Version 1.0 feature set and avoids a larger web framework, build pipeline, or JavaScript application.
5.2 Accepted tradeoffs
Version 1.0 starts Flask's built-in server with debug=False, bound to 0.0.0.0:8000. This server is convenient for a prototype but is not a production process manager. It provides no automatic restart, service readiness management, log rotation, or resource policy.
Gunicorn is declared in requirements.txt, but the implemented entry point and autostart entry do not use it.
6. Selection of Chromium kiosk mode
6.1 Rationale
Chromium turns the locally served web page into a full-screen appliance display. It provides mature HTML/CSS rendering, image support, automatic page refresh, and kiosk presentation without requiring a dedicated native GUI.
Hosting and displaying the page on the same Pi provides a simple loopback path:
Chromium -> http://127.0.0.1:8000 -> Flask
The browser's kiosk and incognito options reduce visible browser controls and avoid dependence on a persistent browser profile.
6.2 Accepted tradeoffs
Chromium requires a graphical desktop session, display compositor, sufficient memory, and a logged-in user session. The browser and Flask server are separate processes, but Version 1.0 does not supervise either one. A browser crash, Flask crash, desktop logout, or display-server failure requires operator intervention.
7. System architecture
7.1 System context
+------------------------- Raspberry Pi --------------------------+
|                                                                  |
|  +-------------------+       HTTP        +-------------------+   |
|  | Chromium kiosk    | <---------------> | Flask application |   |
|  | 127.0.0.1:8000    |                   | 0.0.0.0:8000       |   |
|  +-------------------+                   +---------+---------+   |
|                                                    |             |
|                                           gspread / HTTPS        |
+----------------------------------------------------|-------------+
                                                     |
                                                     v
                                          +--------------------+
                                          | Google Sheets API  |
                                          | Google spreadsheet |
                                          +--------------------+
7.2 Repository components
Component	Responsibility
fids_display.py	Entry point, Flask routes, Google access, data transformation, inline HTML/CSS, static routing, and server startup
config.py	Spreadsheet key, departure worksheet name, and refresh interval
requirements.txt	Direct Python dependencies
fids_autostart.desktop	Intended desktop-session startup of Flask and Chromium
static/favicon.ico	Browser and title fallback icon
static/logos/*.png	Airline logos keyed by IATA-style flight prefix
.gitignore	Excludes virtual environments, credentials, keys, and local artifacts

7.3 Runtime processes
The intended deployment uses these processes:
A Raspberry Pi graphical desktop session.
A POSIX shell launched by the desktop autostart mechanism.
A Python process running the Flask application.
A Chromium process displaying the local page.
No dedicated system service is implemented.
8. Application design
8.1 Entry point
Running python3 fids_display.py executes:
app.run(host="0.0.0.0", port=8000, debug=False)
The application directory is derived from the resolved location of fids_display.py. Static files and credentials are located relative to that directory.
8.2 HTTP interface
Method and route	Behavior
GET /	Reads and displays the worksheet named by SHEET_NAME
GET /arrival	Reads SHEET_NAME_ARRIVAL, or Arrival when that setting is absent
GET /favicon.ico	Returns static/favicon.ico
GET /static/...	Served by Flask's static-file handling

There is no health endpoint, API endpoint, authentication layer, or write operation.
8.3 Request and data flow
For each request to / or /arrival, the application:
Checks for service_account.json in the application directory.
Constructs a new gspread service-account client.
Opens the spreadsheet by SHEET_KEY.
Selects the requested worksheet by name.
Calls get_all_values() to retrieve the complete used worksheet as strings.
Treats the first row as headers and all remaining rows as flights.
Maps worksheet columns into the fixed display schema.
Renders the inline Jinja template.
Returns a complete HTML document.
There is no cross-request Google client reuse or data cache.
8.4 Worksheet schema discovery
Column lookup is case-insensitive after surrounding whitespace is removed.
Display field	Recognized worksheet headings
Flight	flight, 便名, 便, flt
Scheduled time	time, sched, std, 予定, 出発時刻
ETD	etd, estimate, estimated, 推定, 見込み
Gate	gate, g, ゲート
Status	status, remark, remarks, 状態, ステータス
Destination	destination, to, 行先, 行き先, dest

If Destination is not recognized, the first column not already assigned to Flight, Time, ETD, Gate, or Status is selected. Missing fields render as empty strings. Extra source columns are ignored.
The normalized output schema is always:
Logo | Flight | Destination | Time | ETD | Gate | Status
8.5 Airline logo handling
The application extracts leading alphabetic characters from the flight value and converts them to uppercase. For example, JL999 selects /static/logos/JL.png.
Version 1.0 includes CX.png, JL.png, KE.png, NH.png, and OZ.png. An unknown carrier attempts to fall back to /static/logos/default.png; that fallback file is not present in the Version 1.0 repository. The header attempts to load MKM.png, which is also absent, and then falls back to the favicon.
8.6 Time and ETD behavior
Times are parsed by splitting a string on : and converting both parts to integers. Values are compared as hour * 60 + minute. No date, timezone, range, or day-rollover validation is performed.
Missing ETD with a valid scheduled time displays an em dash.
ETD equal to scheduled time displays an em dash.
ETD numerically later than scheduled time receives class etd-delay.
ETD numerically earlier than scheduled time receives class etd-early.
An unparseable value is treated as unavailable.
The Version 1.0 stylesheet does not define visual rules for etd-delay or etd-early.
8.7 Status behavior
Status classification uses case-insensitive substring matching:
Condition	CSS class	Intended color
Contains on time, boarding, or departed	ok	Green
Contains delay	delay	Yellow
Contains cancel	cancel	Red
Anything else	none	Normal text

8.8 Refresh cycle
The page contains an HTML meta-refresh value derived from UPDATE_INTERVAL, which defaults to 30 seconds. Chromium reloads the current route after that period, causing a new full Google Sheets read and complete page render.
Code for alternating between departure and arrival routes is present in the template but commented out. Version 1.0 therefore remains on whichever route the operator opened.
9. Configuration design
9.1 Implemented configuration
config.py defines:
Setting	Version 1.0 value	Purpose
SHEET_KEY	Committed spreadsheet identifier	Google spreadsheet to open
SHEET_NAME	Departure	Worksheet displayed at /
UPDATE_INTERVAL	30	Browser refresh interval in seconds

SHEET_NAME_ARRIVAL is optional and defaults to Arrival when its import raises an exception.
9.2 Hard-coded configuration
The following cannot be configured without implementation changes:
service-account filename and location;
bind address;
TCP port;
static directory;
Google authorization scopes; and
kiosk URL in the committed desktop entry.
The README's suggestion that credentials can be placed outside the repository or selected through environment variables is not implemented in Version 1.0.
10. External dependencies
10.1 Direct Python packages
Package	Pinned version	Role
Flask	3.0.3	Web server, routing, rendering, and static files
gspread	6.1.4	Google Sheets API wrapper
google-auth	2.35.0	Google credential support
google-auth-oauthlib	1.2.1	OAuth integration required by gspread
google-auth-httplib2	0.2.0	Installed authentication transport; unused by application code
Gunicorn	23.0.0	Installed WSGI server; unused by the Version 1.0 startup path

Transitive dependencies are not locked and may vary by installation date.
10.2 Operating-system dependencies
Raspberry Pi OS with a graphical desktop
Python 3.8 or later
Python virtual-environment support
pip
POSIX shell
Chromium or chromium-browser
desktop autologin or an interactive desktop login
display server/compositor
system fonts with the required Latin and Japanese glyphs
DNS, TLS certificate store, network connectivity, and accurate system time
No GPIO, camera, serial, I2C, SPI, or other Raspberry Pi-specific hardware interface is used.
11. Raspberry Pi deployment architecture
11.1 Intended filesystem layout
The committed desktop entry assumes:
~/PiFIDS/
├── config.py
├── fids_display.py
├── requirements.txt
├── service_account.json
└── static/
The repository README creates .venv beneath the project directory, although the desktop entry does not invoke that environment's interpreter.
11.2 Intended startup sequence
The desktop entry attempts to:
change to ~/PiFIDS;
start /usr/bin/python3 fids_display.py in the background;
wait six seconds; and
launch Chromium against http://127.0.0.1:8000.
11.3 Known autostart limitation
The committed Exec value is not operational as written. It contains both non-standard single-quote argument handling for a desktop entry and invalid shell syntax in:
(chromium-browser || chromium) --kiosk ...
It also invokes /usr/bin/python3 instead of .venv/bin/python. Consequently, Version 1.0's application can be operated manually, but its committed unattended-start mechanism is not a reliable deployment mechanism. This limitation is part of the Version 1.0 baseline and is not silently corrected by this specification.
12. Network requirements
12.1 Required outbound connectivity
The Raspberry Pi requires:
DNS resolution;
HTTPS access on TCP 443 to Google authentication and Google API services;
access to the configured Google spreadsheet; and
working system time for TLS and signed service-account assertions.
Google service endpoints can change; firewall rules should follow Google's published service requirements rather than rely on a single fixed IP address.
12.2 Local connectivity
Chromium connects to 127.0.0.1:8000. No inbound Internet connection is required for the kiosk itself.
Because Flask binds to 0.0.0.0, port 8000 is also reachable through every active Pi network interface unless the host firewall or network segmentation blocks it. This is broader than the kiosk's loopback-only requirement.
12.3 Behavior during loss of connectivity
If Google cannot be reached during a refresh, the route returns an HTTP 500 page containing the exception message. Version 1.0 does not continue displaying the previous successful dataset.
13. Installation procedure
This procedure documents a manual Version 1.0 installation without changing its implementation.
13.1 Prerequisites
Install a Raspberry Pi OS desktop image.
Configure display resolution, locale, timezone, keyboard, network, and desktop login.
Ensure Python 3, virtual-environment support, pip, Chromium, and suitable Japanese fonts are installed.
Confirm that the Pi can resolve and reach Google HTTPS services.
13.2 Application installation
Place the repository at ~/PiFIDS if the committed path convention is to be retained.

From the repository directory, create and activate a virtual environment:
python3 -m venv .venv
source .venv/bin/activate

Install the declared dependencies:
pip install -r requirements.txt

Create or select the Google spreadsheet.

Ensure it has Departure and, if required, Arrival worksheets with recognizable headers.

Create a Google service account and download its JSON credential.

Share the spreadsheet with the service account email.

Place the credential at ~/PiFIDS/service_account.json and restrict access to the operating user.

Set SHEET_KEY, SHEET_NAME, and UPDATE_INTERVAL in config.py as required.

13.3 Verification
With the virtual environment active:
python3 fids_display.py
Verify:
http://127.0.0.1:8000/ displays departures;
http://127.0.0.1:8000/arrival displays arrivals;
airline logos load for supported codes;
the page reloads at the configured interval; and
a spreadsheet edit becomes visible after a subsequent refresh.
13.4 Kiosk launch
After the Flask server is responding, launch the locally available Chromium executable with kiosk and incognito options against:
http://127.0.0.1:8000
The exact browser executable name is OS-image dependent. The committed combined fallback expression must not be treated as a valid shell command.
14. Operating procedure
14.1 Normal startup
Power on the display and Raspberry Pi.
Wait for the graphical desktop and network to become available.
Open a terminal in ~/PiFIDS.
Activate .venv.
Start python3 fids_display.py.
Confirm that port 8000 is serving the display.
Start Chromium in kiosk mode at the departure or arrival route.
14.2 Normal data operation
Authorized staff update the Google worksheet. The kiosk reflects changes on the next browser refresh. Operators should retain the configured headings and expected time format.
14.3 Selecting a display
Departure: http://127.0.0.1:8000/
Arrival: http://127.0.0.1:8000/arrival
The display does not alternate automatically.
14.4 Normal shutdown
Close Chromium or leave kiosk mode.
Stop the Flask process with an interrupt from its terminal.
Shut down Raspberry Pi OS cleanly before removing power.
15. Failure behavior and recovery
Version 1.0 recovery is manual. The following table records observable behavior and the operator response.
Failure	Implemented behavior	Operator recovery
Missing credential file	HTTP 500 and traceback output	Restore service_account.json at the application root and verify permissions
Invalid/revoked credential	HTTP 500	Provision a valid credential and re-share the spreadsheet if necessary
Spreadsheet not shared	HTTP 500 from Google/gspread	Share the spreadsheet with the service-account email
Wrong spreadsheet key	HTTP 500	Verify SHEET_KEY
Missing worksheet	HTTP 500	Restore the configured worksheet or correct its configured name
Empty worksheet	HTTP 204; kiosk appears blank	Add a header row and data, then reload
Network or Google outage	HTTP 500 on refresh	Restore connectivity or wait for service recovery, then reload
API quota/rate limit	HTTP 500	Reduce clients/refresh frequency operationally and wait for quota recovery
Flask process exits	Browser cannot connect	Restart Flask from the activated virtual environment
Chromium exits or hangs	Display disappears/freezes	Restart Chromium and reopen the required route
Unknown airline code	Broken logo after missing fallback	Continue without a logo; Version 1.0 has no default image file
Invalid time value	ETD comparison silently degrades	Correct worksheet time values to HH:MM
Pi loses power	Abrupt stop; possible filesystem risk	Restore power, verify filesystem and credentials, then restart processes

No automatic retry, watchdog, last-known-good cache, or failover server is implemented.
16. Security considerations
16.1 Credential protection
service_account.json contains a private key. It is excluded by .gitignore, but Version 1.0 does not enforce file permissions, secret rotation, external secret storage, or runtime injection. Access should be limited to the dedicated Pi user. The credential must never be committed or copied into support bundles.
16.2 Google authorization scope
The default gspread service-account scopes permit more access than the display requires. The service account should therefore be dedicated to Pi-FIDS and shared only with the necessary spreadsheet. Read-only scope enforcement is a future implementation item.
16.3 Worksheet content trust
Version 1.0 renders transformed worksheet cells with Jinja's safe filter. A user able to edit the sheet can inject HTML or JavaScript into the kiosk page. Spreadsheet editor access must therefore be treated as application-administrator access.
16.4 Network exposure
The Flask server has no authentication and listens on all interfaces. It should be protected by host firewall rules, a trusted local network, or network segmentation. Port 8000 should not be forwarded from the public Internet.
16.5 Error disclosure
HTTP 500 responses contain raw exception text, and tracebacks are printed to the process output. These can expose filesystem paths, worksheet details, and operational context. Access to both port 8000 and application logs should be restricted.
16.6 Browser security
The kiosk runs local content but retrieves data controlled by spreadsheet editors. Incognito mode limits persistent browser state; it does not sandbox malicious worksheet HTML from the page itself.
16.7 Dependency and asset governance
Direct Python packages are pinned, but transitive packages are not locked. Version 1.0 has no automated vulnerability scanning or software-bill-of-materials generation. The repository also does not document licenses or permission for the included airline images and contains no project license file.
17. Performance and capacity characteristics
Every browser refresh performs a new authentication/client construction and full worksheet read. Load therefore scales with:
number of browser clients x refresh frequency x worksheet size
The design is suitable for one local kiosk and a modest worksheet. It is not intended for many clients, large sheets, or low-latency operational flight feeds. No formal response-time, memory, availability, or capacity targets are defined for Version 1.0.
18. Compatibility baseline
18.1 Raspberry Pi OS Bullseye
The application source and pinned packages are compatible with Bullseye's Python 3.9 when installed in a virtual environment. The committed autostart limitations still apply.
18.2 Raspberry Pi OS Bookworm
The application source and declared packages are compatible with Python 3.11, but the deployment is not Bookworm-ready as committed. Bookworm requires pip-managed packages to be installed in a virtual environment, while the desktop entry calls /usr/bin/python3. Modern Raspberry Pi desktop kiosk startup also differs from the committed entry.
18.3 Later Python releases
The packages declare no relevant upper Python bound, but Version 1.0 has no automated compatibility tests. Python versions later than 3.11 are unverified.
19. Known Version 1.0 limitations
Desktop autostart is not operational as committed.
Credential-location documentation and implementation disagree.
Google data is fetched synchronously for every request.
No offline or stale-data display exists.
No process supervision or automatic restart exists.
No tests or continuous integration exist.
Worksheet content is trusted as safe HTML.
Flask listens on all interfaces without authentication.
Google authorization is not least-privilege.
Missing default.png produces broken unknown-airline logos.
Missing MKM.png causes a favicon fallback in the title.
ETD comparison does not understand dates or midnight rollover.
ETD classification classes have no visual styling.
Transitive dependencies are not locked.
Fonts and image licensing are not documented.
The project has no declared software license.
20. Future roadmap
Future work is divided into four phases. None of these items is implemented by Version 1.0.
Phase 1 — Preserve Version 1.0 behavior
Establish a known-good Bullseye hardware and OS baseline.
Add characterization tests without changing visible behavior.
Record the worksheet schema and example datasets.
Capture reference screenshots for visual comparison.
Produce reproducible dependency and installation records.
Document credentials, assets, fonts, startup, and rollback.
Phase 2 — Prepare for Raspberry Pi OS Bookworm
Use the project virtual environment consistently at runtime.
Introduce supervised application startup and restart behavior.
Separate the Flask service from graphical kiosk startup.
Implement the appropriate labwc/desktop autostart procedure.
Add network readiness and HTTP health checks.
Verify Chromium executable names and flags.
Test on required arm64 and armhf targets.
Define logging and CJK font installation.
Phase 3 — Improve application architecture
Separate configuration, Google access, transformation, routes, templates, and static styling.
Add validated configuration and an explicit worksheet schema.
Use read-only Google scopes and a reusable client.
Escape worksheet content and remove unsafe HTML injection paths.
Add retry/backoff, caching, last-known-good data, and stale-data indicators.
Add structured logging, readiness, health, and graceful error pages.
Add unit, integration, visual, and browser tests.
Add CI, dependency locking, vulnerability scanning, and license documentation.
Phase 4 — Optional Docker support
Containerize only the Flask application by default.
Run as a non-root user with credentials mounted as secrets.
Provide ARM-compatible images, health checks, and Compose configuration.
Keep Chromium and desktop-session control on the Raspberry Pi host.
Document container networking, logs, updates, and rollback.
21. Version 1.0 conformance statement
A deployment conforms to this Version 1.0 design when it:
runs the baseline fids_display.py implementation without behavioral modification;
reads the configured Google spreadsheet through a service account;
exposes departure at / and arrival at /arrival;
renders the fixed seven-column display schema;
uses the configured browser refresh interval;
serves included static assets from the application directory; and
uses Chromium or an equivalent browser to display the local Flask route.
Operational scripts, firewall rules, filesystem permissions, and manual startup procedures may surround the implementation, but they do not become Version 1.0 application features unless incorporated into a later controlled implementation baseline.
22. Reference material
Pi-FIDS repository: https://github.com/MasahiroSuzuki5062/pi-fids
Flask documentation: https://flask.palletsprojects.com/
gspread documentation: https://docs.gspread.org/
Raspberry Pi OS documentation: https://www.raspberrypi.com/documentation/computers/os.html
Raspberry Pi kiosk guide: https://www.raspberrypi.com/tutorials/how-to-use-a-raspberry-pi-in-kiosk-mode/
Desktop Entry specification: https://specifications.freedesktop.org/desktop-entry-spec/latest/















承認を依頼

5.5中
