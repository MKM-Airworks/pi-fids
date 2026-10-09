"""Separate read-only LAN feed; the management UI stays on localhost."""
import json
from urllib.parse import parse_qs, urlparse

from .__main__ import ROOT, handler


def manager_handler(store, security, upstream=None, os_clock=None):
    from .backup import Backups, MAX_BYTES, inspect_archive, private
    import sqlite3
    import zipfile
    import uuid
    import re
    backups=Backups(store,security,upstream)
    class ManagerHandler(handler(store, upstream, os_clock)):
        def do_GET(self):
            path = urlparse(self.path).path
            if path == '/login':
                return self.send(200, (ROOT/'templates/login.html').read_bytes(), 'text/html; charset=utf-8')
            if path == '/api/session':
                return self.send(200, {'authenticated':security.session(self.headers), 'airport':security.config()['airport'], 'secured':True,'user':security.identity(self.headers),'setupRequired':security.setup_required()})
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
            identity=security.identity(self.headers)
            if path in ('/api/users','/api/audit','/api/audit-settings','/api/clock','/api/backups','/api/backups/download','/backup-guide') and identity['role']!='admin':
                return self.send(403,{'error':'Administrator access required'})
            if path in ('/api/backups','/api/backups/download'):
                try:
                    if path=='/api/backups':return self.send(200,backups.status())
                    identifier=parse_qs(urlparse(self.path).query).get('id',[''])[0]
                    return self.send(200,backups.path(identifier).read_bytes(),'application/zip')
                except (ValueError,OSError):return self.send(400,{'error':'Backup not found'})
            if path=='/api/users':
                return self.send(200,security.listing())
            if path=='/api/audit':
                try:
                    query=parse_qs(urlparse(self.path).query)
                    airport=query.get('airport',[security.config()['airport']])[0]
                    if airport != security.config()['airport']:return self.send(403,{'error':'Airport access denied'})
                    cursor=query.get('beforeId',[None])[0]
                    return self.send(200,store.audit_records(airport,int(cursor) if cursor else None))
                except ValueError as error:return self.send(400,{'error':str(error)})
            scoped_paths = ('/api/audit-settings','/api/airport-names', '/api/clock', '/api/registry', '/api/state', '/api/assets', '/api/feed', '/api/display', '/api/upstream', '/asset', '/display')
            airport = parse_qs(urlparse(self.path).query).get('airport', ['SHI'])[0] if path in scoped_paths else security.config()['airport']
            if airport != security.config()['airport']:
                return self.send(403, {'error':'Airport access denied'})
            return super().do_GET()

        def do_POST(self):
            if self.path=='/api/backups/upload':
                origin=self.headers.get('Origin')
                if origin and origin!='http://'+self.headers.get('Host',''):return self.send(403,{'error':'Invalid origin'})
                identity=security.identity(self.headers)
                if not identity:return self.send(401,{'error':'Please sign in'})
                if identity['role']!='admin':return self.send(403,{'error':'Administrator access required'})
                if self.headers.get('Content-Type')!='application/zip':return self.send(415,{'error':'ZIP required'})
                path=None
                try:
                    size=int(self.headers.get('Content-Length','0'))
                    if not 0<size<=MAX_BYTES:raise ValueError('Backup is too large or empty')
                    identifier=uuid.uuid4().hex
                    path=backups.root/(identifier+'.upload')
                    private(path,b'')
                    remaining=size
                    with path.open('wb') as file:
                        while remaining:
                            block=self.rfile.read(min(1024*1024,remaining))
                            if not block:raise ValueError('Incomplete upload')
                            file.write(block);remaining-=len(block)
                    result=inspect_archive(path,security.config()['airport'])
                    with store.as_actor(identity):store.record_audit(security.config()['airport'],'backup.inspect',identifier,None,{'createdAt':result['createdAt']})
                    return self.send(200,{'id':identifier,**result})
                except (ValueError,OSError,sqlite3.Error,zipfile.BadZipFile,KeyError,TypeError,AttributeError):
                    if path:path.unlink(missing_ok=True)
                    return self.send(400,{'error':'Backup validation failed. Check the file, airport and software version.'})
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.send(415, {'error':'JSON required'})
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + self.headers.get('Host', ''):
                return self.send(403, {'error':'Invalid origin'})
            if self.path in ('/api/login','/api/setup-admin'):
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= 4096:
                        raise ValueError('Invalid request size')
                    data = json.loads(self.rfile.read(size))
                    if self.path=='/api/setup-admin':
                        if self.client_address[0]!='127.0.0.1':return self.send(403,{'error':'Local setup only'})
                        security.bootstrap(data.get('username'),data.get('password'))
                        with store.as_actor({'username':data['username'],'role':'admin'}):
                            store.record_audit(security.config()['airport'],'user.bootstrap',data['username'],None,{'role':'admin','active':True})
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
            identity=security.identity(self.headers)
            operator_paths={'/api/flights','/api/flights/update','/api/flights/delete','/api/publish','/api/upstream/check','/api/upstream/import','/api/signage'}
            if identity['role']!='admin' and self.path not in operator_paths:
                return self.send(403,{'error':'Administrator access required'})
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
                data=json.loads(body)
                with store.as_actor(identity):
                    if self.path in ('/api/backups/create','/api/backups/prepare'):
                        try:
                            if self.path.endswith('/create'):
                                result=backups.create()
                                store.record_audit(security.config()['airport'],'backup.create',result['id'],None,{'createdAt':result['createdAt']})
                            else:
                                identifier=data.get('id')
                                if not isinstance(identifier,str) or not re.fullmatch('[a-f0-9]{32}',identifier):raise ValueError('Invalid backup ID')
                                source=backups.root/(identifier+'.upload')
                                target=backups.root/('recovery-'+identifier)
                                result=inspect_archive(source,security.config()['airport'],target)
                                result['folder']=str(target)
                                store.record_audit(security.config()['airport'],'backup.prepare',identifier,None,{'createdAt':result['createdAt']})
                            return self.send(200,result)
                        except (ValueError,OSError,sqlite3.Error,zipfile.BadZipFile,KeyError,TypeError,AttributeError):return self.send(400,{'error':'Backup or recovery preparation failed. Live data was not replaced.'})
                    if self.path=='/api/users':
                        before,after=security.change_user(data)
                        store.record_audit(security.config()['airport'],'user.'+data['action'],data['username'],before,after)
                        return self.send(200,{'ok':True})
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
                references = {(feed['control'].get('signage') or {}).get('defaultImage',''), feed['control']['logo'], feed['control']['image'], (feed['control'].get('board') or {}).get('logo','')} | {flight.get('airlineLogo', '') for flight in feed['flights']} | {item.get('logo','') for item in feed.get('airlineNames',{}).values()}
                if not digest or digest not in references:
                    return self.send(403, {'error':'Image is not part of this published display'})
                mime, body = store.asset(airport, digest)
                self.send(200, body, mime)
            except ValueError as error:
                self.send(400, {'error':str(error)})
    return FeedHandler
