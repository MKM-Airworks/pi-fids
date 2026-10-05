"""Separate read-only LAN feed; the management UI stays on localhost."""
import json
from urllib.parse import parse_qs, urlparse

from .__main__ import ROOT, handler


def manager_handler(store, security, upstream=None):
    class ManagerHandler(handler(store, upstream)):
        def do_GET(self):
            path = urlparse(self.path).path
            if path == '/login':
                return self.send(200, (ROOT/'templates/login.html').read_bytes(), 'text/html; charset=utf-8')
            if path == '/api/session':
                return self.send(200, {'authenticated':security.session(self.headers), 'airport':security.config()['airport'], 'secured':True})
            if path.startswith('/static/'):
                return super().do_GET()
            if not security.session(self.headers):
                if path.startswith('/api/') or path == '/asset':
                    return self.send(401, {'error':'Please sign in on the management PC.'})
                self.send_response(303)
                self.send_header('Location', '/login')
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                return
            scoped_paths = ('/api/state', '/api/assets', '/api/feed', '/api/display', '/api/upstream', '/asset', '/display')
            airport = parse_qs(urlparse(self.path).query).get('airport', ['SHI'])[0] if path in scoped_paths else security.config()['airport']
            if airport != security.config()['airport']:
                return self.send(403, {'error':'Airport access denied'})
            return super().do_GET()

        def do_POST(self):
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.send(415, {'error':'JSON required'})
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + self.headers.get('Host', ''):
                return self.send(403, {'error':'Invalid origin'})
            if self.path == '/api/login':
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= 4096:
                        raise ValueError('Invalid request size')
                    data = json.loads(self.rfile.read(size))
                    token = security.login(data.get('username'), data.get('password'), self.client_address[0])
                except (ValueError, AttributeError):
                    return self.send(400, {'error':'Invalid login request'})
                if not token:
                    return self.send(401, {'error':'Sign-in failed. Check credentials or try again in one minute.'})
                self.send_response(200)
                self.send_header('Set-Cookie', 'pifids_session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800')
                self.send_header('Content-Length','2')
                self.send_header('Cache-Control','no-store')
                self.end_headers()
                self.wfile.write(b'{}')
                return
            if not security.session(self.headers):
                return self.send(401, {'error':'Please sign in on the management PC.'})
            if self.path == '/api/logout':
                security.logout(self.headers)
                self.send_response(200)
                self.send_header('Set-Cookie','pifids_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
                self.send_header('Content-Length','2')
                self.send_header('Cache-Control','no-store')
                self.end_headers()
                self.wfile.write(b'{}')
                return
            # Inspect airport before the existing write handler consumes the body.
            import io
            original = self.rfile
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= (3*1024*1024 if self.path == '/api/assets' else 16384):
                    raise ValueError('Invalid request size')
                body = original.read(size)
                if json.loads(body).get('airport') != security.config()['airport']:
                    return self.send(403, {'error':'Airport access denied'})
                self.rfile = io.BytesIO(body)
                return super().do_POST()
            except (ValueError, AttributeError):
                return self.send(400, {'error':'Invalid request'})
            finally:
                self.rfile = original
    return ManagerHandler


def feed_handler(store, security):
    class FeedHandler(handler(store)):
        def do_POST(self):
            self.send(405, {'error':'LAN feed is read-only'})

        def do_GET(self):
            url = urlparse(self.path)
            if url.path not in ('/api/feed', '/asset'):
                return self.send(404, {'error':'LAN feed has no management UI or draft API'})
            identity = security.terminal(self.headers)
            if identity is None:
                return self.send(401, {'error':'Invalid terminal credentials'})
            airport, display_id = identity
            query = parse_qs(url.query)
            if query.get('airport', [''])[0] != airport or query.get('displayId', [''])[0] != display_id:
                return self.send(403, {'error':'Terminal identity mismatch'})
            try:
                feed = store.feed(airport, display_id)
                if url.path == '/api/feed':
                    return self.send(200, feed)
                digest = query.get('id', [''])[0]
                references = {feed['control']['logo'], feed['control']['image']} | {flight.get('airlineLogo', '') for flight in feed['flights']}
                if not digest or digest not in references:
                    return self.send(403, {'error':'Image is not part of this published display'})
                mime, body = store.asset(airport, digest)
                self.send(200, body, mime)
            except ValueError as error:
                self.send(400, {'error':str(error)})
    return FeedHandler
