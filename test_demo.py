import hashlib, http.client, json, os, tempfile, threading, unittest
from datetime import datetime, timedelta
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from unittest.mock import patch
from zoneinfo import ZoneInfo
import demo

class TestDemo(unittest.TestCase):
 def test_import_and_switch(self):
    day=datetime.now(ZoneInfo(demo.ZONE)).date().isoformat()
    tomorrow=(datetime.fromisoformat(day)+timedelta(days=1)).date().isoformat()
    scope=dict(organizationId='00000000-0000-4000-8000-000000000001',airportId='00000000-0000-4000-8000-000000000002',product='pi-fids',stationAirport='ROR',timezone=demo.ZONE)
    identity=dict(scope,schemaVersion='mkm-fids-distribution/1',releaseId='00000000-0000-4000-8000-000000000003',dataVersion=1,publishedAt=day+'T00:00:00Z',preview=False,coverage={'from':day,'to':tomorrow})
    raw=json.dumps(dict(identity,declaration='schedules',flights=[dict(id='demo',flightNumber='ZZ123',airlineCode='ZZ',origin='ROR',destination='GUM',journeyType='international',validFrom=day,validTo=tomorrow,operatingDays=list(range(1,8)),status='NA',codeshareFlights=[],direction='departure',scheduledTime='23:59',estimatedTime='',gate='1',timeStatus='',boardingStatus='')])).encode()
    path='/v1/fids-receiver/releases/'+identity['releaseId']
    manifest=dict(identity,localDate=day,status='available',activeScheduleCount=1,sha256=hashlib.sha256(raw).hexdigest(),byteLength=len(raw),dataPath=path)
    upstream_token='U'*40
    class Fixture(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.headers.get('Authorization')!='Bearer '+upstream_token:
                self.send_error(401);return
            body=raw if self.path==path else json.dumps(manifest).encode()
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(body)
        def log_message(self,*a):pass
    with tempfile.TemporaryDirectory() as tmp, ThreadingHTTPServer(('127.0.0.1',0),Fixture) as f:
      threading.Thread(target=f.serve_forever,daemon=True).start()
      try:
        # Permit HTTP only for this isolated fixture; deployment requires HTTPS.
        from pifids.upstream import Upstream
        orig=Upstream.connection
        def local(self):
            source, expected, token=orig(self)
            return 'http://127.0.0.1:'+str(f.server_port),expected,token
        origin='https://demo.example'
        env=dict(DEMO_ORIGIN=origin,DEMO_DATA_DIR=tmp,DEMO_ADMIN_PASSWORD='test-password-only',DEMO_DISPLAY_TOKEN='D'*40,ROR_FDD_TOKEN=upstream_token,ROR_FDD_ORIGIN='https://fixture.example',ROR_FDD_ORG_ID=scope['organizationId'],ROR_FDD_AIRPORT_ID=scope['airportId'])
        with patch.dict(os.environ,env),patch.object(Upstream,'connection',local):
          with ThreadingHTTPServer(('127.0.0.1',0),demo.build()) as s:
            threading.Thread(target=s.serve_forever,daemon=True).start()
            def req(path,data=None,**headers):
                c=http.client.HTTPConnection('127.0.0.1',s.server_port,timeout=5)
                if data is not None:headers.update({'Content-Type':'application/json','Origin':origin})
                c.request('GET' if data is None else 'POST',path,None if data is None else json.dumps(data),headers)
                r=c.getresponse(); payload=r.read(); cookie=r.getheader('Set-Cookie');c.close()
                return r.status,payload,cookie
            try:
                self.assertEqual(req('/api/demo-mode',{'mode':'gate'})[0],403)
                code,_,cookie=req('/api/login',dict(username='demo-admin',password=env['DEMO_ADMIN_PASSWORD']))
                self.assertEqual(code,200);self.assertIn('Secure',cookie)
                auth={'Cookie':cookie.split(';')[0]}
                for endpoint,data in [('check',dict(airport='ROR')),('import',dict(airport='ROR',serviceDate=day,expectedDraftRevision=0,webVersion=1))]:
                    r=req('/api/upstream/'+endpoint,data,**auth);self.assertEqual(r[0],200,r)
                self.assertEqual(req('/api/publish',dict(airport='ROR'),**auth)[0],200)
                code, raw_schedule, _ = req('/api/demo-seasonal', **auth)
                self.assertEqual(code, 200, raw_schedule)
                self.assertIn(b'demo-seasonal.js', req('/', **auth)[1])
                schedule = json.loads(raw_schedule)
                from seasonal_editor import FIELDS
                fields = {key:schedule['flights'][0].get(key, '') for key in FIELDS}
                fields['scheduledTime'] = '20:00'
                edit = dict(id='demo', revision=schedule['revision'], fields=fields, serviceDate=tomorrow)
                self.assertEqual(req('/api/demo-seasonal/save', edit)[0], 403)
                code, body, _ = req('/api/demo-seasonal/preview', edit, **auth)
                self.assertEqual(code, 200, body)
                self.assertEqual(json.loads(body)['flights'][0]['time'], '20:00')
                self.assertEqual(req('/api/demo-seasonal/save', edit, **auth)[0], 200)
                self.assertEqual(req('/api/demo-seasonal/save', edit, **auth)[0], 409)
                self.assertIn(b'schedule.seasonal-edit', req('/api/audit?airport=ROR', **auth)[1])
                self.assertEqual(json.loads(req('/api/state?airport=ROR', **auth)[1])['flights'][0]['time'], '23:59')
                self.assertEqual(req('/api/upstream/mode', {'airport':'ROR','mode':'auto'}, **auth)[0], 403)
                terminal={'Authorization':'Bearer '+'D'*40}
                query='?airport=ROR&displayId=ror-demo'
                for mode in ('board','counter','gate','board'):
                    self.assertEqual(req('/api/demo-mode',{'mode':mode},**auth)[0],200)
                    code,raw_feed,_=req('/api/feed'+query,**terminal)
                    self.assertEqual(code,200);feed=json.loads(raw_feed)
                    self.assertEqual(feed['control']['mode'],mode)
                    self.assertEqual(feed['flights'][0]['flightNumber'],'ZZ123')
                    if mode!='board':self.assertEqual(req('/asset'+query+'&id='+feed['control']['image'],**terminal)[0],200)
                self.assertEqual(req('/api/feed?airport=SHI&displayId=ror-demo',**terminal)[0],403)
                self.assertEqual(req('/api/publish',dict(airport='ROR'),**terminal)[0],401)
                from pifids.daily import DailySchedules
                from pifids.store import Store
                from pifids.upstream import Upstream
                from seasonal_editor import SeasonalEditor
                from pathlib import Path
                store = Store(str(Path(tmp) / 'demo.sqlite'))
                store.installed_airport = 'ROR'
                editor = SeasonalEditor(store, 'ROR', Upstream(store, Path(tmp) / 'fdd.json'))
                rollover = DailySchedules(store, editor.for_rollover)
                rollover.step(datetime.fromisoformat(day+'T23:59:00').replace(tzinfo=ZoneInfo(demo.ZONE)))
                self.assertEqual(store.read('ROR')['flights'][0]['time'], '23:59')
                rollover.step(datetime.fromisoformat(tomorrow+'T00:00:00').replace(tzinfo=ZoneInfo(demo.ZONE)))
                self.assertTrue(any(row['time']=='20:00' and row['serviceDate']==tomorrow
                                    for row in store.read('ROR')['flights']))

            finally:s.shutdown()
      finally:f.shutdown()
