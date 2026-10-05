import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .store import Store, DraftConflict

ROOT = Path(__file__).resolve().parent


def handler(store):
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
            files = {'/': ('templates/manager.html', 'text/html'), '/display': ('templates/display.html', 'text/html'), '/static/app.js': ('static/app.js', 'text/javascript'), '/sw.js': ('static/sw.js', 'text/javascript'), '/static/manager-i18n.js': ('static/manager-i18n.js', 'text/javascript'), '/static/display.css': ('static/display.css', 'text/css'), '/static/style.css': ('static/style.css', 'text/css')}
            files['/static/login.js'] = ('static/login.js', 'text/javascript')
            if url.path in files:
                path, mime = files[url.path]
                self.send(200, (ROOT / path).read_bytes(), mime + '; charset=utf-8')
            elif url.path == '/api/session':
                self.send(200, {'authenticated':True, 'airport':None, 'secured':False})
            elif url.path == '/api/feed':
                try:
                    query = parse_qs(url.query)
                    self.send(200, store.feed(query.get('airport', ['SHI'])[0], query.get('displayId', ['default'])[0]))
                except ValueError as error:
                    self.send(400, {'error':str(error)})
            elif url.path == '/api/state':
                try:
                    self.send(200, store.read(parse_qs(url.query).get('airport', ['SHI'])[0]))
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
                if self.path == '/api/flights':
                    store.add(data)
                elif self.path == '/api/flights/update':
                    store.change_flight(data)
                elif self.path == '/api/flights/delete':
                    store.change_flight(data, delete=True)
                elif self.path == '/api/publish':
                    store.publish(data.get('airport'))
                elif self.path == '/api/display':
                    store.set_display(data)
                else:
                    return self.send(404, {'error': 'Not found'})
                self.send(200, {'ok': True})
            except DraftConflict as error:
                self.send(409, {'error': str(error)})
            except (ValueError, TypeError, AttributeError) as error:
                self.send(400, {'error': str(error)})
    return Handler


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Local-only Pi-FIDS V2 prototype')
    parser.add_argument('--port', type=int, default=8800)
    parser.add_argument('--database', default=str(Path.home() / '.pifids-v2' / 'prototype.sqlite'))
    parser.add_argument('--auth-config', help='Local manager login and terminal credentials file')
    parser.add_argument('--lan-port', type=int, help='Enable separate read-only LAN feed (requires auth configuration)')
    parser.add_argument('--lan-host', default='0.0.0.0', help='Address for the read-only LAN feed only')
    args = parser.parse_args()
    if args.lan_port and not args.auth_config:
        parser.error('LAN feed requires --auth-config')
    store = Store(args.database)
    management = handler(store)
    if args.auth_config:
        from .security import Security
        from .lan import manager_handler, feed_handler
        security = Security(args.auth_config)
        management = manager_handler(store, security)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), management)
    if args.lan_port:
        lan_server = ThreadingHTTPServer((args.lan_host, args.lan_port), feed_handler(store, security))
        threading.Thread(target=lan_server.serve_forever, daemon=True).start()
        print('Read-only LAN feed on port %s (terminal credentials required)' % args.lan_port, flush=True)
    print('Pi-FIDS V2 prototype: http://127.0.0.1:%s' % args.port, flush=True)
    server.serve_forever()
