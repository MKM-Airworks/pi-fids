import base64
import hashlib
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from pifids.lan import feed_handler, manager_handler
from pifids.receiver import ReceiverStore, sync_once
from pifids.security import Security, password_hash, write_private
from pifids.store import Store
from test_assets import png


class LanTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)
        self.token = 'synthetic-terminal-credential-for-tests-only'
        self.config_path = self.path/'auth.json'
        salt = '01'*16
        self.config = {'airport':'ROR', 'username':'test', 'salt':salt,
                       'passwordHash':password_hash('synthetic-test-password', salt),
                       'terminals':{'gate-01':hashlib.sha256(self.token.encode()).hexdigest()}}
        write_private(self.config_path, self.config, exclusive=True)
        self.security = Security(self.config_path)
        self.store = Store(self.path/'manager.sqlite')
        self.source = self.start(feed_handler(self.store, self.security))
        self.manager = self.start(manager_handler(self.store, self.security))

    def start(self, handler):
        class Quiet(handler):
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1',0), Quiet)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def close():
            server.shutdown()
            server.server_close()
            thread.join()
        self.addCleanup(close)
        return 'http://127.0.0.1:'+str(server.server_port)

    def request(self, source, path, data=None, headers=None):
        headers = dict(headers or {})
        if data is not None:
            headers['Content-Type'] = 'application/json'
            data = json.dumps(data).encode()
        return urlopen(Request(source+path, data=data, headers=headers), timeout=3)

    def denied(self, code, source, path, data=None, headers=None):
        with self.assertRaises(HTTPError) as caught:
            self.request(source,path,data,headers)
        self.assertEqual(caught.exception.code, code)
        caught.exception.close()

    def credentials(self):
        return {'Authorization':'Bearer '+self.token}

    def test_lan_contains_no_manager_or_drafts_and_requires_terminal_identity(self):
        self.store.add({'airport':'ROR','flightNumber':'DRAFT','destination':'Tokyo','time':'10:00'})
        path = '/api/feed?airport=ROR&displayId=gate-01'
        self.denied(401,self.source,path)
        self.denied(403,self.source,'/api/feed?airport=SHI&displayId=gate-01',headers=self.credentials())
        self.denied(403,self.source,'/api/feed?airport=ROR&displayId=other',headers=self.credentials())
        for forbidden in ('/','/api/state?airport=ROR','/api/assets?airport=ROR','/static/app.js','/display'):
            self.denied(404,self.source,forbidden,headers=self.credentials())
        self.denied(405,self.source,'/api/flights',{},self.credentials())
        with self.request(self.source,path,headers=self.credentials()) as response:
            feed = json.load(response)
        self.assertNotIn('draft',feed)
        self.assertEqual(feed['flights'],[])
        self.assertEqual(feed['control']['displayId'],'gate-01')

    def test_receiver_syncs_published_images_and_retains_disk_on_revocation(self):
        digest = self.store.upload_asset({'airport':'ROR','name':'test.png','body':base64.b64encode(png()).decode()})
        self.store.add({'airport':'ROR','flightNumber':'PUB','destination':'Tokyo','time':'10:00','airlineLogo':digest})
        self.denied(403,self.source,'/asset?airport=ROR&displayId=gate-01&id='+digest,headers=self.credentials())
        self.store.publish('ROR')
        self.store.set_display({'airport':'ROR','displayId':'gate-01','mode':'gate','airline':'Test Air','logo':digest})
        receiver = ReceiverStore(self.path/'receiver.sqlite')
        sync_once(receiver,self.source,'ROR','gate-01',self.token)
        self.assertEqual(receiver.read('ROR')['flights'][0]['flightNumber'],'PUB')
        self.assertEqual(receiver.read('ROR')['draft'],[])
        self.assertEqual(receiver.asset('ROR',digest)[1],png())
        self.assertEqual(receiver.display('ROR','gate-01')['airline'],'Test Air')
        self.config['terminals'] = {}
        write_private(self.config_path,self.config)
        with self.assertRaises(HTTPError):
            sync_once(receiver,self.source,'ROR','gate-01',self.token)
        self.assertEqual(ReceiverStore(self.path/'receiver.sqlite').read('ROR')['version'],1)

    def test_manager_login_airport_scope_origin_and_logout(self):
        self.denied(401,self.manager,'/api/state?airport=ROR')
        self.denied(401,self.manager,'/api/flights',{})
        self.denied(401,self.manager,'/api/login',{'username':'test','password':'wrong'})
        self.denied(403,self.manager,'/api/login',{'username':'test','password':'synthetic-test-password'}, {'Origin':'http://untrusted.example'})
        with self.request(self.manager,'/api/login',{'username':'test','password':'synthetic-test-password'}) as response:
            cookie = response.headers['Set-Cookie']
        self.assertIn('HttpOnly',cookie)
        self.assertIn('SameSite=Strict',cookie)
        headers = {'Cookie':cookie.split(';')[0]}
        with self.request(self.manager,'/api/flights',{'airport':'ROR','flightNumber':'TEST','destination':'Guam','time':'12:00'},headers) as response:
            self.assertEqual(response.status,200)
        self.assertEqual(len(self.store.read('ROR')['draft']),1)
        self.denied(403,self.manager,'/api/state?airport=SHI',headers=headers)
        self.denied(403,self.manager,'/api/state',headers=headers)
        self.denied(403,self.manager,'/api/flights',{'airport':'SHI'},headers)
        with self.request(self.manager,'/api/logout',{},headers) as response:
            self.assertEqual(response.status,200)
        self.denied(401,self.manager,'/api/state?airport=ROR',headers=headers)

    def test_login_attempt_limit(self):
        for _ in range(5):
            self.assertIsNone(self.security.login('test','wrong','synthetic-peer'))
        self.assertIsNone(self.security.login('test','synthetic-test-password','synthetic-peer'))
        self.assertIsNotNone(self.security.login('test','synthetic-test-password','different-peer'))

    def test_local_prototype_receiver_remains_compatible(self):
        from pifids.__main__ import handler
        self.store.add({'airport':'SHI','flightNumber':'LOCAL','destination':'Tokyo','time':'10:00'})
        self.store.publish('SHI')
        source = self.start(handler(self.store))
        receiver = ReceiverStore(self.path/'local.sqlite')
        sync_once(receiver,source,'SHI','board')
        self.assertEqual(receiver.read('SHI')['flights'][0]['flightNumber'],'LOCAL')

    def test_redirect_is_rejected_without_sending_credentials_to_target(self):
        from http.server import BaseHTTPRequestHandler
        class Redirect(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header('Location','http://127.0.0.1:1/')
                self.end_headers()
        source = self.start(Redirect)
        with self.assertRaisesRegex(ValueError,'redirects'):
            sync_once(ReceiverStore(self.path/'redirect.sqlite'),source,'ROR','gate-01',self.token)


if __name__ == '__main__':
    unittest.main()
