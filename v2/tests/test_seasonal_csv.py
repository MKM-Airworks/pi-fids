import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime
from pifids.store import Store,DraftConflict
from pifids.seasonal_csv import parse,preview,import_draft
from pifids.daily import DailySchedules
HEADER='carrier,number,movement,origin,destination,geo,validFrom,validTo,daysText,time,sta,codeshares\n'
CSV=HEADER+'UA,158,DEP,ROR,GUM,INTL,2026-10-01,2026-10-31,1234567,02:05,,\nUA,157,ARR,GUM,ROR,INTL,2026-10-01,2026-10-31,1234567,,00:50,\n'
class CsvTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=Store(Path(self.temp.name)/'manager.sqlite');self.store.configure_site('ROR','Pacific/Palau')
        self.data={'airport':'ROR','csv':CSV,'serviceDate':'2026-10-05','expectedDraftRevision':0}
    def test_bom_direction_and_preview_do_not_write(self):
        result=preview(self.store,{**self.data,'csv':'\ufeff'+CSV})
        self.assertEqual(result['scheduleCount'],2)
        self.assertEqual([(r['flightNumber'],r['destination'],r['time']) for r in result['flights']],[('UA157','GUM','00:50'),('UA158','GUM','02:05')])
        self.assertTrue(all(row['geo']=='INTL' for row in result['flights']))
        self.assertEqual(self.store.read('ROR')['draft'],[])
    def test_wrong_scope_bad_time_days_and_overlap_rejected(self):
        for raw in [CSV.replace(',ROR,',',SHI,'),CSV.replace('02:05','24:05'),CSV.replace('1234567','11'),CSV+CSV.splitlines()[1]+'\n',CSV.replace('2026-10-31','2026-09-30')]:
            with self.assertRaises(ValueError):parse(raw,'ROR','Pacific/Palau')
    def test_conflict_atomicity_and_local_audit(self):
        self.store.add({'airport':'ROR','flightNumber':'LOCAL','destination':'GUM','serviceDate':'2026-10-05','time':'12:00'})
        with self.assertRaises(DraftConflict):import_draft(self.store,self.data)
        self.assertEqual(len(self.store.read('ROR')['draft']),1)
        import_draft(self.store,{**self.data,'expectedDraftRevision':self.store.read('ROR')['draftRevision']})
        self.assertEqual(len(self.store.read('ROR')['draft']),3)
        self.assertEqual(self.store.read('ROR')['flights'],[])
        self.assertEqual(self.store.audit_records('ROR')[0]['source'],'CSV seasonal schedule')
    def test_offline_previous_evening_and_midnight_generation(self):
        import_draft(self.store,self.data);self.store.publish('ROR')
        with self.store.connect() as db:db.execute('INSERT INTO board_settings VALUES (?,?,?)',('ROR','display',json.dumps({'departureShowMinutes':360})))
        daily=DailySchedules(self.store)
        daily.step(datetime.fromisoformat('2026-10-05T20:04:59+09:00'))
        self.assertFalse(any(r['serviceDate']=='2026-10-06' for r in self.store.read('ROR')['flights']))
        daily.step(datetime.fromisoformat('2026-10-05T20:05:00+09:00'))
        self.assertEqual(sum(r['serviceDate']=='2026-10-06' for r in self.store.read('ROR')['flights']),1)
        daily.step(datetime.fromisoformat('2026-10-06T00:00:00+09:00'))
        self.assertEqual({r['serviceDate'] for r in self.store.read('ROR')['flights']},{'2026-10-06'})
        self.assertEqual(len(self.store.read('ROR')['flights']),2)

    def test_seasonal_cache_survives_validated_backup_restore(self):
        from pifids.security import Security,write_private,password_hash
        from pifids.backup import Backups,inspect_archive
        import_draft(self.store,self.data);self.store.publish('ROR');DailySchedules(self.store)
        root=Path(self.temp.name);salt='01'*16;auth=root/'auth.json'
        write_private(auth,{'airport':'ROR','timezone':'Pacific/Palau','username':'admin','salt':salt,'passwordHash':password_hash('synthetic-password',salt),'terminals':{}})
        backups=Backups(self.store,Security(auth));result=backups.create();folder=root/'restored'
        inspect_archive(backups.path(result['id']),'ROR',folder)
        restored=Store(folder/'manager.sqlite');DailySchedules(restored).step(datetime.fromisoformat('2026-10-06T00:00:00+09:00'))
        self.assertEqual({r['serviceDate'] for r in restored.read('ROR')['flights']},{'2026-10-06'})

    def test_reimport_keeps_prepared_future_operator_changes(self):
        import_draft(self.store,self.data);self.store.publish('ROR')
        with self.store.connect() as db:db.execute('INSERT INTO board_settings VALUES (?,?,?)',('ROR','display',json.dumps({'departureShowMinutes':360})))
        DailySchedules(self.store).step(datetime.fromisoformat('2026-10-05T20:05:00+09:00'))
        current=self.store.read('ROR');future=next(r for r in current['draft'] if r['serviceDate']=='2026-10-06')
        self.store.change_flight({**future,'gate':'7','expectedDraftRevision':current['draftRevision']})
        import_draft(self.store,{**self.data,'expectedDraftRevision':self.store.read('ROR')['draftRevision']})
        self.assertEqual(next(r for r in self.store.read('ROR')['draft'] if r['serviceDate']=='2026-10-06')['gate'],'7')
