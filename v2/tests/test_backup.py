import base64
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import zipfile
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from pifids.backup import Backups, inspect_archive, encoded, digest
from pifids.security import Security, password_hash, write_private
from pifids.store import Store
from pifids.upstream import init_tables
from pifids import registry
from test_assets import png
import test_lan

class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        salt='01'*16
        self.auth=self.root/'auth.json'
        write_private(self.auth,{'airport':'SHI','timezone':'Asia/Tokyo','username':'admin','salt':salt,'passwordHash':password_hash('synthetic-admin-password',salt),'terminals':{'counter-01':hashlib.sha256(b'synthetic-terminal-key').hexdigest()}})
        self.security=Security(self.auth);self.security.change_user({'action':'create','username':'operator','password':'synthetic-operator-password','role':'operator'})
        self.store=Store(self.root/'manager.sqlite');registry.init(self.store);init_tables(self.store)
        logo=self.store.upload_asset({'airport':'SHI','name':'logo.png','body':base64.b64encode(png()).decode()})
        self.store.add({'airport':'SHI','flightNumber':'TEST1','destination':'Tokyo','time':'10:00','airlineLogo':logo});self.store.publish('SHI')
        registry.save_terminal(self.store,{'airport':'SHI','displayId':'counter-01','name':'Counter','usage':'signage','defaultImage':logo})
        self.store.save_audit_retention('SHI',168)
        with self.store.connect() as db:db.execute("INSERT INTO upstream_sync (airport,mode) VALUES ('SHI','auto')")
        self.service=Backups(self.store,self.security)

    def archive(self):
        return self.service.path(self.service.create()['id'])

    def rewrite(self,path,mutate):
        with zipfile.ZipFile(path) as z:payload={n:z.read(n) for n in z.namelist()}
        mutate(payload)
        out=self.root/'modified.zip'
        with zipfile.ZipFile(out,'w') as z:
            for name,body in payload.items():z.writestr(name,body)
        return out

    def rehash(self,payload,name,body):
        payload[name]=body;manifest=json.loads(payload['manifest.json']);manifest['files'][name]={'bytes':len(body),'sha256':digest(body)};payload['manifest.json']=encoded(manifest)

    def test_roundtrip_snapshot_users_images_and_live_data_unchanged(self):
        original=self.store.feed('SHI','counter-01');archive=self.archive()
        self.store.add({'airport':'SHI','flightNumber':'NEW2','destination':'Kobe','time':'11:00'})
        target=self.root/'recovered';summary=inspect_archive(archive,'SHI',target)
        self.assertEqual(summary['flights'],1);self.assertEqual(summary['images'],1);self.assertEqual(summary['users'],2)
        restored=Store(target/'manager.sqlite');restored_feed=restored.feed('SHI','counter-01');original.pop('clock');restored_feed.pop('clock');self.assertEqual(restored_feed,original)
        self.assertEqual(len(self.store.read('SHI')['draft']),2)
        self.assertEqual(restored.audit_retention('SHI')['hours'],168)
        self.assertEqual(registry.listing(restored,'SHI')['terminals'][0]['name'],'Counter')
        recovered_security=Security(target/'manager-auth.json')
        self.assertEqual(recovered_security.sessions,{})
        self.assertIsNotNone(recovered_security.login('operator','synthetic-operator-password','test'))
        with restored.connect() as db:self.assertEqual(db.execute("SELECT mode FROM upstream_sync WHERE airport='SHI'").fetchone()[0],'manual')
        with self.assertRaises(ValueError):inspect_archive(archive,'SHI',target)
        with self.assertRaises(ValueError):inspect_archive(archive,'ROR',self.root/'wrong-airport')
        self.assertFalse((self.root/'wrong-airport').exists())
        self.assertNotIn(b'synthetic-terminal-key',archive.read_bytes())

    def test_tampered_checksum_traversal_and_missing_image_rejected(self):
        archive=self.archive()
        bad=self.rewrite(archive,lambda p:p.update({'manager.sqlite':p['manager.sqlite']+b'bad'}))
        with self.assertRaises(ValueError):inspect_archive(bad,'SHI',self.root/'bad')
        bad=self.rewrite(archive,lambda p:p.update({'../escape':b'bad'}))
        with self.assertRaises(ValueError):inspect_archive(bad,'SHI')
        def corrupt(p):
            dbpath=self.root/'tampered.sqlite';dbpath.write_bytes(p['manager.sqlite'])
            with sqlite3.connect(dbpath) as db:db.execute('DELETE FROM assets')
            self.rehash(p,'manager.sqlite',dbpath.read_bytes())
        bad=self.rewrite(archive,corrupt)
        with self.assertRaisesRegex(ValueError,'image'):inspect_archive(bad,'SHI')
        self.assertFalse((self.root/'bad').exists())

    def test_archive_schema_and_no_administrator_rejected(self):
        archive=self.archive()
        def malicious(p):
            dbpath=self.root/'malicious.sqlite';dbpath.write_bytes(p['manager.sqlite'])
            with sqlite3.connect(dbpath) as db:db.execute('CREATE TRIGGER evil AFTER INSERT ON state BEGIN DELETE FROM assets; END')
            self.rehash(p,'manager.sqlite',dbpath.read_bytes())
        with self.assertRaisesRegex(ValueError,'schema'):inspect_archive(self.rewrite(archive,malicious),'SHI')
        def no_admin(p):
            users=json.loads(p['manager-auth.users.json']);users['admin']['active']=False
            self.rehash(p,'manager-auth.users.json',encoded(users))
        with self.assertRaisesRegex(ValueError,'administrator'):inspect_archive(self.rewrite(archive,no_admin),'SHI')

    def test_web_secret_is_not_included_and_moved_paths_work(self):
        class Upstream:pass
        upstream=Upstream();upstream.path=self.root/'web.json'
        upstream.path.write_text(json.dumps({'baseUrl':'https://example.invalid','expected':{'stationAirport':'SHI','product':'pi-fids'},'credentialFile':'original-secret-path.json','token':'synthetic-web-secret'}))
        service=Backups(self.store,self.security,upstream);archive=service.path(service.create()['id'])
        with zipfile.ZipFile(archive) as z:
            self.assertFalse(any(b'synthetic-web-secret' in z.read(n) or b'original-secret-path' in z.read(n) for n in z.namelist()))
            self.assertEqual(json.loads(z.read('web-connection.template.json'))['credentialFile'],'web-credential.json')
        self.assertTrue(inspect_archive(archive,'SHI')['webReconfigurationRequired'])

class BackupApiTests(test_lan.LanTests):
    def cookie(self,name='test',password='synthetic-test-password'):
        with self.request(self.manager,'/api/login',{'username':name,'password':password}) as r:return {'Cookie':r.headers['Set-Cookie'].split(';')[0]}

    def test_admin_create_upload_inspect_prepare_and_roles(self):
        admin=self.cookie()
        with self.request(self.manager,'/api/users',{'airport':'ROR','action':'create','username':'op','password':'synthetic-operator-password','role':'operator'},admin):pass
        op=self.cookie('op','synthetic-operator-password')
        for route in ('/api/backups','/api/backups/download?id='+'0'*32):self.denied(403,self.manager,route,headers=op)
        for route in ('/api/backups/create','/api/backups/prepare'):self.denied(403,self.manager,route,{'airport':'ROR'},op)
        self.denied(401,self.manager,'/api/backups/create',{'airport':'ROR'})
        self.denied(403,self.manager,'/api/backups/create',{'airport':'SHI'},admin)
        self.denied(403,self.manager,'/api/backups/create',{'airport':'ROR'},{**admin,'Origin':'http://evil.invalid'})
        with self.request(self.manager,'/api/backups/create',{'airport':'ROR'},admin) as r:created=json.load(r)
        with self.request(self.manager,'/api/backups',headers=admin) as r:listing=json.load(r)
        self.assertIn(created['id'],[item['id'] for item in listing['backups']])
        with self.request(self.manager,'/api/backups/download?id='+created['id'],headers=admin) as r:body=r.read()
        request=Request(self.manager+'/api/backups/upload',data=body,headers={**admin,'Content-Type':'application/zip'})
        with urlopen(request,timeout=5) as r:reviewed=json.load(r)
        for headers in ({'Content-Type':'application/zip'},{**op,'Content-Type':'application/zip'},{**admin,'Content-Type':'application/zip','Origin':'http://evil.invalid'}):
            with self.assertRaises(HTTPError) as error:urlopen(Request(self.manager+'/api/backups/upload',data=body,headers=headers),timeout=3)
            self.assertIn(error.exception.code,(401,403))
        with self.request(self.manager,'/api/backups/prepare',{'airport':'ROR','id':reviewed['id']},admin) as r:prepared=json.load(r)
        self.assertTrue(Path(prepared['folder'],'manager.sqlite').exists())
        self.denied(400,self.manager,'/api/backups/prepare',{'airport':'ROR','id':reviewed['id']},admin)
        actions=[r['action'] for r in self.store.audit_records('ROR')]
        self.assertIn('backup.create',actions);self.assertIn('backup.inspect',actions);self.assertIn('backup.prepare',actions)
        self.denied(404,self.source,'/api/backups',headers=self.credentials())

if __name__=='__main__':unittest.main()
