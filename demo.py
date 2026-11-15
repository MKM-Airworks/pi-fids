"""Isolated Render entry point for the Pi-FIDS ROR demo."""
import base64
import hashlib
import json
import os
import secrets
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from pifids.daily import DailySchedules
from pifids.downloads import display_package, serve_display_download
from pifids.lan import manager_handler, feed_handler
from pifids.security import Security, password_hash, write_private
from pifids.store import Store
from pifids.upstream import Upstream

AIRPORT, ZONE, DISPLAY = 'ROR', 'Pacific/Palau', 'ror-demo'
ROOT = Path(__file__).resolve().parent


def build(*, start_daily=False):
    origin = os.environ['DEMO_ORIGIN'].rstrip('/')
    parsed = urlsplit(origin)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username
            or parsed.password or parsed.path or parsed.query or parsed.fragment):
        raise ValueError('DEMO_ORIGIN must be the HTTPS origin')
    data = Path(os.environ['DEMO_DATA_DIR'])
    data.mkdir(parents=True, exist_ok=True)
    password, key = os.environ['DEMO_ADMIN_PASSWORD'], os.environ['DEMO_DISPLAY_TOKEN']
    Security.validate_user('demo-admin', password, 'admin')
    upstream_key = os.environ['ROR_FDD_TOKEN']
    if len(key) < 32 or not key.isascii() or not key.isprintable() or any(c.isspace() for c in key) or key in (password, upstream_key):
        raise ValueError('Use a distinct display token of at least 32 characters')
    auth = data / 'demo-auth.json'
    salt = secrets.token_hex(16)
    write_private(auth, dict(airport=AIRPORT, timezone=ZONE, username='demo-admin',
                            salt=salt, passwordHash=password_hash(password, salt),
                            terminals={DISPLAY:hashlib.sha256(key.encode()).hexdigest()}))
    store = Store(str(data / 'demo.sqlite'))
    store.configure_site(AIRPORT, ZONE)
    store.installed_airport = AIRPORT
    security = Security(auth)
    credential = (data / 'fdd-credential.json').resolve()
    write_private(credential, {'token':upstream_key})
    config = data / 'fdd.json'
    write_private(config, dict(baseUrl=os.environ['ROR_FDD_ORIGIN'], credentialFile=str(credential),
                               expected=dict(organizationId=os.environ['ROR_FDD_ORG_ID'],
                                             airportId=os.environ['ROR_FDD_AIRPORT_ID'],
                                             product='pi-fids',stationAirport=AIRPORT,timezone=ZONE)))
    upstream = Upstream(store, config)
    package = display_package(ROOT / "dist")
    artwork = {}
    for mode, filename in [('counter','skymark-checkin-test.png'),('gate','skymark-gate-test.png')]:
        artwork[mode] = store.upload_asset(dict(airport=AIRPORT,name=filename,kind='signage',
                                              body=base64.b64encode((ROOT/'artwork'/filename).read_bytes()).decode()))
    if not store.display(AIRPORT, DISPLAY)['version']:
        store.set_display(dict(airport=AIRPORT,displayId=DISPLAY,mode='board'))

    class Demo(manager_handler(store, security, upstream)):
        def log_message(self, *_):
            pass

        def end_headers(self):
            self.send_header('X-Frame-Options','DENY')
            self.send_header('Referrer-Policy','no-referrer')
            super().end_headers()

        def send_header(self, key, value):
            super().send_header(key, value+'; Secure' if key.lower()=='set-cookie' else value)

        def do_GET(self):
            path = urlsplit(self.path).path
            if serve_display_download(self, path, package):
                return
            if path == '/healthz':
                return self.send(200, {'ok':True})
            if path in ('/api/feed','/asset') and self.headers.get('Authorization') is not None:
                return terminal.do_GET(self)
            if path == '/demo' and security.session(self.headers):
                return self.send(200,(ROOT/'demo.html').read_bytes(),'text/html; charset=utf-8')
            if path == '/static/demo.js':
                return self.send(200,(ROOT/'demo.js').read_bytes(),'text/javascript; charset=utf-8')
            return super().do_GET()

        def do_POST(self):
            if self.headers.get('Origin') != origin:
                return self.send(403, {'error':'Invalid origin'})
            if self.path in ('/api/setup-admin','/api/upstream/mode','/api/clock'):
                return self.send(403, {'error':'Unavailable in the Render demo'})
            if self.path == '/api/demo-mode':
                identity = security.identity(self.headers)
                if not identity or identity['role']!='admin':
                    return self.send(403, {'error':'Administrator required'})
                try:
                    size = int(self.headers.get('Content-Length','0'))
                    if not 0 < size <= 1024 or self.headers.get('Content-Type') != 'application/json':
                        raise ValueError()
                    mode = json.loads(self.rfile.read(size))['mode']
                    if mode not in ('board','counter','gate'):
                        raise ValueError()
                except (ValueError, KeyError, TypeError):
                    return self.send(400, {'error':'Invalid display mode'})
                store.set_display(dict(airport=AIRPORT,displayId=DISPLAY,mode=mode,
                                       airline='Skymark Airlines' if mode!='board' else '',
                                       image=artwork.get(mode,'')))
                return self.send(200, {'mode':mode})
            # Existing manager handler checks the same-origin scheme itself.
            self.headers.replace_header('Origin','http://'+self.headers['Host'])
            return super().do_POST()

    terminal = feed_handler(store, security)
    if start_daily:
        DailySchedules(store).start()
    return Demo


if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0',int(os.environ.get('PORT','10000'))), build(start_daily=True)).serve_forever()
