import base64
import json
import tempfile
import unittest
from pathlib import Path
from pifids.store import Store
from pifids.asset_catalog import catalog, delete
from test_assets import png
from pifids import registry, board_config, signage_config


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=Store(Path(self.tmp.name)/'db.sqlite')
        self.digest=self.store.upload_asset({'airport':'ROR','name':'example.png','body':base64.b64encode(png()).decode(),'kind':'logo'})
        registry.init(self.store)

    def item(self):return next(x for x in catalog(self.store,'ROR') if x['digest']==self.digest)

    def test_unused_delete_is_scoped_and_audited(self):
        item=self.item();self.assertEqual((item['width'],item['height']),(1,1));self.assertTrue(item['canDelete'])
        with self.assertRaises(ValueError):delete(self.store,{'airport':'SHI','digest':self.digest})
        self.assertEqual(self.store.asset('ROR',self.digest)[0],'image/png')
        with self.store.as_actor({'username':'admin-test','role':'admin'}):delete(self.store,{'airport':'ROR','digest':self.digest})
        self.assertEqual(len(catalog(self.store,'ROR')),1)
        self.assertFalse(catalog(self.store,'ROR')[0]['canDelete'])
        self.assertEqual(self.store.audit_records('ROR')[0]['actor'],'admin-test')
        with self.assertRaises(ValueError):delete(self.store,{'airport':'ROR','digest':'builtin-default'})

    def test_all_live_assignments_prevent_deletion(self):
        self.store.add({'airport':'ROR','flightNumber':'UA1','destination':'GUM','time':'10:00','airlineLogo':self.digest})
        self.store.publish('ROR')
        self.store.save_airline_name({'airport':'ROR','code':'UA','names':{'en':'United','logo':self.digest}})
        self.store.set_display({'airport':'ROR','displayId':'counter','mode':'counter','airline':'United','logo':self.digest})
        with self.store.connect() as db:
            board_config.write(db,'ROR','board',{'direction':'arrival','logo':self.digest})
            signage_config.write(db,'ROR','counter',{'enabled':True,'defaultImage':self.digest,'start':'','end':'','date':''})
            db.execute('INSERT INTO signage_profiles VALUES (?,?,?,?,?,?)',('ROR','United Counter','counter','United',self.digest,''))
        item=self.item();self.assertFalse(item['canDelete'])
        self.assertEqual({x['kind'] for x in item['usage']},{'draft','published','airline','terminal','profile'})
        self.assertTrue(any(x['field']=='defaultImage' for x in item['usage']))
        with self.assertRaisesRegex(ValueError,'in use'):delete(self.store,{'airport':'ROR','digest':self.digest})
        self.assertEqual(self.store.asset('ROR',self.digest)[1],png())

    def test_unused_after_default_assignment_is_removed(self):
        with self.store.connect() as db:
            signage_config.write(db,'ROR','counter',{'enabled':True,'defaultImage':self.digest,'start':'','end':'','date':''})
        with self.assertRaises(ValueError):delete(self.store,{'airport':'ROR','digest':self.digest})
        with self.store.connect() as db:
            signage_config.write(db,'ROR','counter',{'enabled':True,'defaultImage':'','start':'','end':'','date':''})
        delete(self.store,{'airport':'ROR','digest':self.digest})
        self.assertEqual(self.store.assets('ROR'),[])
