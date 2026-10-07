import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .store import Store, DraftConflict
from . import registry, clock_sync

ROOT = Path(__file__).resolve().parent


def handler(store, upstream=None, os_clock=None):
    class Handler(BaseHTTPRequestHandler):
        def send(self, status, body, mime='application/json; charset=utf-8'):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlparse(self.path)
            files = {'/static/manager.css': ('static/manager.css', 'text/css'), '/static/board-policy.js': ('static/board-policy.js', 'text/javascript'), '/': ('templates/manager.html', 'text/html'), '/display': ('templates/display.html', 'text/html'), '/static/app.js': ('static/app.js', 'text/javascript'), '/sw.js': ('static/sw.js', 'text/javascript'), '/static/manager-i18n.js': ('static/manager-i18n.js', 'text/javascript'), '/static/display.css': ('static/display.css', 'text/css'), '/static/style.css': ('static/style.css', 'text/css')}
            files['/static/airport-names.js'] = ('static/airport-names.js', 'text/javascript')
            files['/static/login.js'] = ('static/login.js', 'text/javascript')
            files['/static/login.css'] = ('static/login.css', 'text/css')
            files['/static/branding/airport-bg.png'] = ('static/branding/airport-bg.png', 'image/png')
            files['/static/branding/mkm-airworks-horizontal.png'] = ('static/branding/mkm-airworks-horizontal.png', 'image/png')
            if url.path in files:
                path, mime = files[url.path]
                self.send(200, (ROOT / path).read_bytes(), mime if mime.startswith('image/') else mime + '; charset=utf-8')
            elif url.path == '/api/session':
                self.send(200, {'authenticated':True, 'airport':None, 'secured':False})
            elif url.path == '/api/upstream':
                try:
                    query = parse_qs(url.query)
                    self.send(200, upstream.info(query.get('airport',['SHI'])[0],query.get('serviceDate',[None])[0]) if upstream else {'configured':False})
                except (ValueError, TypeError, KeyError) as error:
                    self.send(400, {'error':str(error)})
            elif url.path == '/api/feed':
                try:
                    query = parse_qs(url.query)
                    self.send(200, store.feed(query.get('airport', ['SHI'])[0], query.get('displayId', ['default'])[0]))
                except ValueError as error:
                    self.send(400, {'error':str(error)})
            elif url.path == '/api/state':
                try:
                    self.send(200, {**store.read(parse_qs(url.query).get('airport', ['SHI'])[0]),'clock':store.clock()})
                except ValueError as error:
                    self.send(400, {'error': str(error)})
            elif url.path in ('/api/assets', '/asset'):
                try:
                    query = parse_qs(url.query)
                    airport = query.get('airport', ['SHI'])[0]
                    if url.path == '/api/assets':
                        self.send(200, store.assets(airport))
                    else:
                        mime, body = store.asset(airport, query.get('id', [''])[0])
                        self.send(200, body, mime)
                except ValueError as error:
                    self.send(400, {'error': str(error)})
            elif url.path == '/api/clock':
                result={**store.clock(),'osClockConfigured':os_clock is not None and getattr(os_clock,'can_set',True),'osClockAvailable':False}
                if os_clock:
                    try:
                        result['osClockStatus']=os_clock.status();result['osClockAvailable']=getattr(os_clock,'can_set',True)
                    except ValueError:
                        result['osClockError']='OS clock service is unavailable'
                self.send(200,result)
            elif url.path == '/api/registry':
                try:
                    self.send(200, registry.listing(store,parse_qs(url.query).get('airport',['SHI'])[0]))
                except ValueError as error:
                    self.send(400, {'error':str(error)})
            elif url.path == '/api/display':
                try:
                    query = parse_qs(url.query)
                    self.send(200, store.display(query.get('airport', ['SHI'])[0], query.get('displayId', ['default'])[0]))
                except ValueError as error:
                    self.send(400, {'error': str(error)})
            else:
                self.send(404, {'error': 'Not found'})

        def do_POST(self):
            # Local prototype: JSON-only requests and same-origin writes.
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.send(415, {'error': 'JSON required'})
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + self.headers.get('Host', ''):
                return self.send(403, {'error': 'Invalid origin'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= (3 * 1024 * 1024 if self.path == '/api/assets' else 16384):
                    raise ValueError('Invalid request size')
                data = json.loads(self.rfile.read(size))
                if self.path == '/api/assets':
                    return self.send(200, {'digest': store.upload_asset(data)})
                if self.path == '/api/airport-names':
                    store.save_airport_name(data)
                elif self.path == '/api/flights':
                    store.add(data)
                elif self.path in ('/api/upstream/check','/api/upstream/import'):
                    if upstream is None:
                        raise ValueError('Web connection is not configured')
                    if self.path.endswith('/check'):
                        upstream.fetch(data.get('airport'))
                    else:
                        upstream.import_draft(data.get('airport'),data.get('serviceDate'),data.get('expectedDraftRevision'),data.get('webVersion'))
                elif self.path == '/api/flights/update':
                    store.change_flight(data)
                elif self.path == '/api/flights/delete':
                    store.change_flight(data, delete=True)
                elif self.path == '/api/publish':
                    store.publish(data.get('airport'))
                elif self.path == '/api/clock':
                    clock_sync.correct_os(store,data,os_clock)
                elif self.path == '/api/terminals':
                    registry.save_terminal(store,data)
                elif self.path == '/api/profiles':
                    registry.save_profile(store,data)
                elif self.path == '/api/signage':
                    registry.apply(store,data)
                elif self.path == '/api/display':
                    store.set_display(data)
                else:
                    return self.send(404, {'error': 'Not found'})
                self.send(200, {'ok': True})
            except DraftConflict as error:
                self.send(409, {'error': str(error)})
            except (ValueError, TypeError, AttributeError, KeyError) as error:
                self.send(400, {'error': str(error)})
    return Handler


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Local-only Pi-FIDS V2 prototype')
    parser.add_argument('--port', type=int, default=8800)
    parser.add_argument('--database', default=str(Path.home() / '.pifids-v2' / 'prototype.sqlite'))
    parser.add_argument('--auth-config', help='Local manager login and terminal credentials file')
    parser.add_argument('--upstream-config', help='Private MKM Flight Web connection JSON')
    parser.add_argument('--clock-service', help='Private loopback Windows OS clock helper connection JSON')
    parser.add_argument('--lan-port', type=int, help='Enable separate read-only LAN feed (requires auth configuration)')
    parser.add_argument('--lan-host', default='0.0.0.0', help='Address for the read-only LAN feed only')
    args = parser.parse_args()
    if args.clock_service and not args.auth_config:
        parser.error('OS clock correction requires manager authentication (--auth-config)')
    if args.lan_port and not args.auth_config:
        parser.error('LAN feed requires --auth-config')
    store = Store(args.database)
    upstream = None
    if args.upstream_config:
        from .upstream import Upstream
        upstream = Upstream(store,args.upstream_config)
    os_clock=None
    if args.clock_service:
        from .os_clock import OsClock
        os_clock=OsClock(args.clock_service)
    else:
        import sys
        if sys.platform == 'win32':
            from .os_clock import WindowsClockStatus
            os_clock=WindowsClockStatus()
    management = handler(store,upstream,os_clock)
    if args.auth_config:
        from .security import Security
        from .lan import manager_handler, feed_handler
        security = Security(args.auth_config)
        if upstream and upstream.connection()[1]['stationAirport'] != security.config()['airport']:
            parser.error('Manager and Web connection airport must match')
        management = manager_handler(store, security,upstream,os_clock)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), management)
    if args.lan_port:
        lan_server = ThreadingHTTPServer((args.lan_host, args.lan_port), feed_handler(store, security))
        threading.Thread(target=lan_server.serve_forever, daemon=True).start()
        print('Read-only LAN feed on port %s (terminal credentials required)' % args.lan_port, flush=True)
    print('Pi-FIDS V2 prototype: http://127.0.0.1:%s' % args.port, flush=True)
    server.serve_forever()
