import json
import unittest
from datetime import date, datetime
from unittest.mock import patch

import test_upstream
from pifids.daily import DailySchedules, carryovers, status


class DailyTests(unittest.TestCase):
    setUp = test_upstream.UpstreamTests.setUp
    stage = test_upstream.UpstreamTests.stage
    def initial(self):
        self.stage()
        self.upstream.import_draft('SHI','2026-10-05',0,1)
        self.store.publish('SHI')
        return self.store.read('SHI')

    def at(self, day='2026-10-06', time='00:00:00'):
        return datetime.fromisoformat(day+'T'+time+'+09:00')

    def test_manual_offline_rollover_without_web_credentials(self):
        before=self.initial()
        self.config_path.unlink();(self.path/'credential.json').unlink()
        daily=DailySchedules(self.store)
        with patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('No network allowed')):
            daily.step(self.at())
        current=self.store.read('SHI')
        self.assertEqual(len(current['flights']),2)
        self.assertEqual({x['serviceDate'] for x in current['flights']},{'2026-10-06'})
        self.assertTrue(set(x['id'] for x in current['flights']).isdisjoint(x['id'] for x in before['flights']))
        with self.store.connect() as db:self.assertEqual(db.execute("SELECT mode FROM upstream_sync WHERE airport='SHI'").fetchone()[0],'manual')
        version=current['version'];daily.step(self.at(time='00:01:00'))
        self.assertEqual(self.store.read('SHI')['version'],version)
        records=[r for r in self.store.audit_records('SHI') if r['action']=='schedule.daily-publish']
        self.assertEqual(len(records),1);self.assertEqual(records[0]['source'],'Saved seasonal schedule')
        self.assertEqual(records[0]['role'],'system')

    def test_cross_midnight_departure_arrival_and_reimport(self):
        current=self.initial()
        for row in current['draft']:
            self.store.change_flight({**row,'estimatedTime':'00:30','estimatedDate':'2026-10-06','gate':'8','expectedDraftRevision':self.store.read('SHI')['draftRevision']})
        self.store.publish('SHI');before=self.store.read('SHI')
        DailySchedules(self.store).step(self.at())
        rows=self.store.read('SHI')['flights']
        self.assertEqual(len(rows),4);self.assertEqual(len(set(x['id'] for x in rows)),4)
        prior=[x for x in rows if x['serviceDate']=='2026-10-05']
        self.assertEqual(prior,before['flights'])
        today=[x for x in rows if x['serviceDate']=='2026-10-06']
        self.assertTrue(all(x['estimatedDate']=='' and x['gate']=='2' for x in today))
        self.upstream.import_draft('SHI','2026-10-06',self.store.read('SHI')['draftRevision'],1)
        self.assertEqual(len(self.store.read('SHI')['draft']),4)
        self.store.publish('SHI')
        # A subsequent Web publication cannot overwrite either previous-day delay.
        self.assertEqual([x for x in self.store.read('SHI')['flights'] if x['serviceDate']=='2026-10-05'],prior)

    def test_retention_and_actual_time_exact_boundaries(self):
        current=self.initial()
        departure=current['flights'][0];arrival=current['flights'][1]
        with self.store.connect() as db:
            db.execute('INSERT INTO display_timing VALUES (?,?,?,?)',('SHI','long-retention',30,180))
            dep={**departure,'estimatedTime':'00:15','estimatedDate':'2026-10-06','actualTime':'00:20','actualDate':'2026-10-06'}
            arr={**arrival,'estimatedTime':'00:15','estimatedDate':'2026-10-06','actualTime':'00:20','actualDate':'2026-10-06'}
            self.assertEqual(carryovers(db,'SHI',[dep,arr],'2026-10-06','Asia/Tokyo',self.at(time='00:49:59')),[dep,arr])
            self.assertEqual(carryovers(db,'SHI',[dep,arr],'2026-10-06','Asia/Tokyo',self.at(time='00:50:00')),[arr])
            self.assertEqual(carryovers(db,'SHI',[dep,arr],'2026-10-06','Asia/Tokyo',self.at(time='03:20:00')),[])

    def test_unpublished_edits_and_expired_cache_preserve_publication(self):
        before=self.initial();row=before['draft'][0]
        self.store.change_flight({**row,'gate':'9','expectedDraftRevision':before['draftRevision']})
        pending=self.store.read('SHI');daily=DailySchedules(self.store);daily.step(self.at())
        self.assertEqual(self.store.read('SHI'),pending)
        self.assertEqual(status(self.store,'SHI')['dailySchedule']['result'],'review_required')
        self.store.publish('SHI');before=self.store.read('SHI')
        daily.step(self.at('2026-10-25'))
        self.assertEqual(self.store.read('SHI'),before)
        self.assertEqual(status(self.store,'SHI')['dailySchedule']['result'],'expired')

    def test_weekday_without_services_clears_only_imported_operations(self):
        body=json.loads(self.raw)
        for row in body['flights']:row['operatingDays']=[1]
        import hashlib
        self.raw=json.dumps(body).encode()
        self.manifest.update(sha256=hashlib.sha256(self.raw).hexdigest(),byteLength=len(self.raw))
        self.initial();self.store.add({'airport':'SHI','flightNumber':'LOCAL','destination':'HND','serviceDate':'2026-10-06','time':'16:00'})
        self.store.publish('SHI');DailySchedules(self.store).step(self.at())
        self.assertEqual([x['flightNumber'] for x in self.store.read('SHI')['flights']],['LOCAL'])

    def test_restart_catches_up_without_creating_missed_days(self):
        self.initial();daily=DailySchedules(self.store);daily.step(self.at('2026-10-08'))
        self.assertEqual({x['serviceDate'] for x in self.store.read('SHI')['flights']},{'2026-10-08'})

    def test_legacy_ids_preserve_same_day_operator_edits(self):
        self.initial()
        with self.store.connect() as db:
            draft=json.loads(db.execute("SELECT draft FROM state WHERE airport='SHI'").fetchone()[0])
            for index,row in enumerate(draft):row['id']=str(index+1)*32
            body=json.dumps(draft)
            db.execute("UPDATE state SET draft=?,published=? WHERE airport='SHI'",(body,body))
            db.execute("UPDATE upstream_imports SET flight_ids=?,baseline=? WHERE airport='SHI'",(json.dumps([x['id'] for x in draft]),body))
        row=self.store.read('SHI')['draft'][0]
        self.store.change_flight({**row,'gate':'9','expectedDraftRevision':self.store.read('SHI')['draftRevision']})
        self.upstream.import_draft('SHI','2026-10-05',self.store.read('SHI')['draftRevision'],1)
        current=self.store.read('SHI')['draft']
        self.assertEqual(len(current),2);self.assertEqual(current[0]['gate'],'9')

    def test_local_airport_midnight_and_no_first_import(self):
        self.stage();daily=DailySchedules(self.store);daily.step(self.at())
        self.assertEqual(self.store.read('SHI')['flights'],[])
        self.assertEqual(status(self.store,'SHI')['dailySchedule']['result'],'waiting_for_first_import')
        self.initial();before=self.store.read('SHI');daily.step(self.at('2026-10-05','23:59:59'))
        self.assertEqual(self.store.read('SHI'),before)
        # 15:00 UTC is exactly midnight in SHI.
        daily.step(datetime.fromisoformat('2026-10-05T15:00:00+00:00'))
        self.assertEqual({x['serviceDate'] for x in self.store.read('SHI')['flights']},{'2026-10-06'})


    def test_future_window_prepares_offline_before_midnight_and_preserves_edits(self):
        self.initial()
        with self.store.connect() as db:
            db.execute('INSERT INTO board_settings VALUES (?,?,?)',('SHI','six-hours',json.dumps({'departureShowMinutes':360})))
        daily=DailySchedules(self.store)
        daily.step(self.at('2026-10-05','23:00:00'))
        # Fixture next-day departure is 10:30, so it has not opened yet.
        self.assertEqual(len(self.store.read('SHI')['flights']),2)
        daily.step(self.at('2026-10-06','04:30:00'))
        self.assertEqual({r['serviceDate'] for r in self.store.read('SHI')['flights']},{'2026-10-06'})
        # Increase window to cover tomorrow's operation before midnight.
        with self.store.connect() as db:
            db.execute('UPDATE board_settings SET body=?',(json.dumps({'departureShowMinutes':1440}),))
        daily.step(self.at('2026-10-06','11:00:00'))
        current=self.store.read('SHI');future=next(r for r in current['draft'] if r['serviceDate']=='2026-10-07')
        self.store.change_flight({**future,'gate':'9','estimatedTime':'11:30','expectedDraftRevision':current['draftRevision']})
        self.store.publish('SHI')
        daily.step(self.at('2026-10-07','00:00:00'))
        rows=self.store.read('SHI')['flights']
        self.assertEqual(len(rows),2)
        self.assertEqual(next(r for r in rows if r['direction']=='departure')['gate'],'9')
        version=self.store.read('SHI')['version'];daily.step(self.at('2026-10-07','00:01:00'))
        self.assertEqual(self.store.read('SHI')['version'],version)

    def test_early_departure_generated_on_previous_evening_without_web(self):
        import hashlib
        body=json.loads(self.raw)
        body['flights'][0]['scheduledTime']='02:05'
        self.raw=json.dumps(body).encode()
        self.manifest.update(sha256=hashlib.sha256(self.raw).hexdigest(),byteLength=len(self.raw))
        self.initial()
        with self.store.connect() as db:
            db.execute('INSERT INTO board_settings VALUES (?,?,?)',('SHI','early',json.dumps({'departureShowMinutes':360})))
        daily=DailySchedules(self.store)
        daily.step(self.at('2026-10-05','20:04:59'))
        self.assertFalse(any(r['serviceDate']=='2026-10-06' for r in self.store.read('SHI')['flights']))
        daily.step(self.at('2026-10-05','20:05:00'))
        future=[r for r in self.store.read('SHI')['flights'] if r['serviceDate']=='2026-10-06']
        self.assertEqual(len(future),1)
        self.upstream.import_draft('SHI','2026-10-05',self.store.read('SHI')['draftRevision'],1)
        self.assertEqual([r for r in self.store.read('SHI')['draft'] if r['serviceDate']=='2026-10-06'],future)

if __name__=='__main__':unittest.main()
