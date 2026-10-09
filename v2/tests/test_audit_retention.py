import tempfile
import unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from pifids.store import Store

class AuditRetentionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=Store(Path(self.temp.name)/'test.sqlite')
    def test_default_boundaries_and_airport_isolation(self):
        now=datetime(2026,10,9,12,tzinfo=timezone.utc)
        self.assertEqual(self.store.audit_retention('SHI')['hours'],72)
        for airport,hours in [('SHI',72),('ROR',168)]:
            self.store.save_audit_retention(airport,hours)
            for age in (hours+1,hours,hours-1):
                self.store.record_audit(airport,'test',str(age))
                with self.store.connect() as db:db.execute('UPDATE audit_log SET occurred_at=? WHERE airport=? AND target=?',((now-timedelta(hours=age)).isoformat(),airport,str(age)))
        self.store.purge_audit(now.isoformat())
        for airport,hours in [('SHI',72),('ROR',168)]:
            targets=[x['target'] for x in self.store.audit_records(airport) if x['action']=='test']
            self.assertEqual(set(targets),{str(hours),str(hours-1)})
        self.assertEqual(Store(self.store.path).audit_retention('ROR')['hours'],168)
    def test_setting_validates_and_immediately_purges(self):
        self.store.record_audit('SHI','test','expired')
        with self.store.connect() as db:db.execute("UPDATE audit_log SET occurred_at='2000-01-01T00:00:00Z'")
        for value in (0,True,'24',25,721,None):
            with self.assertRaises(ValueError):self.store.save_audit_retention('SHI',value)
        self.assertEqual(len(self.store.audit_records('SHI')),1)
        with self.store.as_actor({'username':'test-admin','role':'admin'}):self.store.save_audit_retention('SHI',24)
        records=self.store.audit_records('SHI')
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]['action'],'audit.retention')
        self.assertEqual(records[0]['actor'],'test-admin')
        self.assertEqual(records[0]['before'],{'hours':72})
        self.assertEqual(records[0]['after'],{'hours':24})
        for value in (24,72,168,720):
            self.store.save_audit_retention('SHI',value)
            self.assertEqual(self.store.audit_retention('SHI')['hours'],value)

if __name__=='__main__':unittest.main()
