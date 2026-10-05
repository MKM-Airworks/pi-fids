import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pifids.store import Store, DraftConflict
from pifids.upstream import Upstream, verify, project

FIXTURES=Path(__file__).parent/'fixtures'

def sample(station='SHI',legacy=False):
    manifest=json.loads((FIXTURES/'distribution-v1-manifest.json').read_text())
    raw=(FIXTURES/'distribution-v1-release.json').read_bytes()
    body=json.loads(raw)
    if not legacy:
        body.update(schemaVersion='mkm-fids-distribution/1',product='pi-fids',stationAirport=station,timezone='Pacific/Palau' if station=='ROR' else 'Asia/Tokyo')
        departure=body['flights'][0]
        departure['origin']=station
        departure.update(direction='departure',scheduledTime=departure.pop('scheduledDeparture'),estimatedTime='10:45',gate='2',timeStatus='DL',boardingStatus='boarding')
        body['flights'].append(dict(departure,id='SYNTHETIC-ARR',direction='arrival',flightNumber='BC102',origin='HND',destination=station,scheduledTime='12:00',estimatedTime='12:15',timeStatus='DL',boardingStatus=''))
        raw=(json.dumps(body,separators=(',',':'))+'\n').encode()
        manifest.update({key:body[key] for key in ('schemaVersion','product','stationAirport','timezone')})
        manifest.update(activeScheduleCount=2,dataPath='/v1/fids-receiver/releases/'+body['releaseId'],sha256=hashlib.sha256(raw).hexdigest(),byteLength=len(raw))
    expected={key:body[key] for key in ('organizationId','airportId','product','stationAirport','timezone')}
    return manifest,raw,{**expected,'allowPreview':True}

class UpstreamTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name)
        self.manifest,self.raw,self.expected=sample()
        (self.path/'credential.json').write_text(json.dumps({'token':'synthetic-web-receiver-credential-only-123456'}))
        self.config={'baseUrl':'http://127.0.0.1:8792','allowLoopback':True,'credentialFile':'credential.json','expected':self.expected}
        self.config_path=self.path/'connection.json';self.config_path.write_text(json.dumps(self.config))
        self.store=Store(self.path/'manager.sqlite');self.upstream=Upstream(self.store,self.config_path)
    def stage(self):
        with self.store.connect() as db:
            db.execute('INSERT OR REPLACE INTO upstream_cache VALUES (?,?,?,?)',('SHI',json.dumps(self.manifest),self.raw,'2026-10-05T00:00:00+00:00'))
    def test_legacy_and_departure_arrival_profiles(self):
        manifest,raw,expected=sample(legacy=True)
        self.assertEqual(project(verify(manifest,raw,expected),'2026-10-05')[0]['direction'],'departure')
        for station in ('SHI','ROR'):
            manifest,raw,expected=sample(station)
            rows=project(verify(manifest,raw,expected),'2026-10-05')
            self.assertEqual([row['direction'] for row in rows],['departure','arrival'])
            self.assertEqual((rows[1]['destination'],rows[1]['time'],rows[1]['estimatedTime'],rows[1]['remark']),('HND','12:00','12:15','Delayed'))
    def test_integrity_scope_preview_rollback_and_mutation_rejected(self):
        for changes in ({'sha256':'0'*64},{'byteLength':1},{'stationAirport':'ROR'},{'dataPath':'https://other.example/data'},{'activeScheduleCount':0}):
            with self.assertRaises(ValueError):verify({**self.manifest,**changes},self.raw,self.expected)
        with self.assertRaises(ValueError):verify(self.manifest,self.raw,{**self.expected,'allowPreview':False})
        for previous in ({**self.manifest,'dataVersion':2},{**self.manifest,'sha256':'0'*64}):
            with self.assertRaises(ValueError):verify(self.manifest,self.raw,self.expected,previous)
    def test_weekdays_expiry_and_cancelled_flights(self):
        body=json.loads(self.raw);body['flights'][0]['operatingDays']=[2];body['flights'][1]['status']='CD'
        rows=project(body,'2026-10-05');self.assertEqual(len(rows),1);self.assertEqual(rows[0]['remark'],'Cancelled')
        with self.assertRaises(ValueError):project(body,'2026-10-25')
        self.stage();self.assertFalse(self.upstream.info('SHI','2026-10-25')['canImport'])
    def test_draft_only_import_and_local_settings_survive_reimport(self):
        self.store.add({'airport':'SHI','flightNumber':'LOCAL','direction':'arrival','destination':'ICN','time':'14:00'});self.store.publish('SHI')
        before=self.store.read('SHI');self.stage();self.upstream.import_draft('SHI','2026-10-05',before['draftRevision'],1)
        current=self.store.read('SHI');self.assertEqual(len(current['draft']),3);self.assertEqual(current['flights'],before['flights'])
        with self.assertRaises(DraftConflict):self.upstream.import_draft('SHI','2026-10-05',before['draftRevision'],1)
        flight=next(row for row in current['draft'] if row['flightNumber']=='BC101')
        self.store.change_flight({**flight,'gate':'7','actualTime':'11:30','actualDate':'2026-10-05','languages':['ja','en'],'expectedDraftRevision':current['draftRevision']})
        self.upstream.import_draft('SHI','2026-10-05',self.store.read('SHI')['draftRevision'],1)
        same_day=next(row for row in self.store.read('SHI')['draft'] if row['flightNumber']=='BC101')
        self.assertEqual(same_day['gate'],'7');self.assertEqual(same_day['actualTime'],'11:30');self.assertEqual(same_day['serviceDate'],'2026-10-05')
        self.upstream.import_draft('SHI','2026-10-06',self.store.read('SHI')['draftRevision'],1)
        flight=next(row for row in self.store.read('SHI')['draft'] if row['flightNumber']=='BC101');self.assertEqual(flight['gate'],'2');self.assertEqual(flight['languages'],['ja','en']);self.assertEqual(flight['actualTime'],'');self.assertEqual(flight['actualDate'],'');self.assertEqual(flight['serviceDate'],'2026-10-06')
        self.assertEqual(Upstream(Store(self.path/'manager.sqlite'),self.config_path).info('SHI','2026-10-06')['lastImportDate'],'2026-10-06')
    def test_duplicate_manual_flight_and_wrong_airport_rejected(self):
        self.stage();self.store.add({'airport':'SHI','flightNumber':'BC101','destination':'HND','time':'10:30'});before=self.store.read('SHI')
        with self.assertRaises(ValueError):self.upstream.import_draft('SHI','2026-10-05',before['draftRevision'],1)
        self.assertEqual(self.store.read('SHI'),before)
        with self.assertRaises(ValueError):self.upstream.info('ROR')
    def test_fetch_then_invalid_response_preserves_cache(self):
        from email.message import Message
        class Reply:
            status=200
            headers=Message();headers['Content-Type']='application/json'
            def __init__(self,raw):self.raw=raw
            def read(self,limit):return self.raw[:limit]
            def __enter__(self):return self
            def __exit__(self,*args):return False
        with patch('pifids.upstream.build_opener') as opener:
            opener.return_value.open.side_effect=[Reply(json.dumps(self.manifest).encode()),Reply(self.raw)]
            self.upstream.fetch('SHI');self.assertEqual(opener.return_value.open.call_args_list[0].args[0].full_url,'http://127.0.0.1:8792/v1/fids-receiver/manifest')
        before=self.upstream.cached('SHI')
        with patch('pifids.upstream.build_opener') as opener:
            opener.return_value.open.side_effect=[Reply(json.dumps(self.manifest).encode()),Reply(b'broken')]
            with self.assertRaises(ValueError):self.upstream.fetch('SHI')
        self.assertEqual(self.upstream.cached('SHI'),before);self.assertEqual(self.upstream.info('SHI','2026-10-05')['lastResult'],'failed')
    def test_remote_http_and_wrong_timezone_rejected(self):
        for config in ({**self.config,'baseUrl':'http://192.168.1.20:8792'},{**self.config,'expected':{**self.expected,'timezone':'UTC'}}):
            self.config_path.write_text(json.dumps(config))
            with self.assertRaises(ValueError):Upstream(self.store,self.config_path)

if __name__=='__main__':unittest.main()
