import base64
import tempfile
import unittest
from pathlib import Path
from pifids import registry, signage_config
from pifids.store import Store
from pifids.receiver import ReceiverStore
from test_assets import png

class SignageTests(unittest.TestCase):
    def test_validation(self):
        for patch in ({'start':'10:00'}, {'start':'24:00','end':'12:00'}, {'start':'10:00','end':'10:00'}, {'date':'2026-10-09'}, {'start':'10:00','end':'12:00','date':'2026-02-30'}, {'defaultImage':'bad'}, {'enabled':1}):
            with self.subTest(patch=patch),self.assertRaises(ValueError):signage_config.validate(patch)
        self.assertEqual(signage_config.validate({'start':'23:00','end':'01:00'})['end'],'01:00')
    def test_offline_roundtrip_preserves_default_and_schedule(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(Path(tmp)/'manager.db');r=ReceiverStore(Path(tmp)/'receiver.db')
            image=s.upload_asset({'airport':'SHI','name':'fallback','body':base64.b64encode(png()).decode()})
            terminal=dict(airport='SHI',displayId='counter-1',name='Counter',usage='signage',defaultImage=image)
            registry.save_terminal(s,terminal)
            registry.save_profile(s,dict(airport='SHI',name='Test Check-In',mode='counter',airline='Test',image='',logo=''))
            registry.apply(s,dict(airport='SHI',displayId='counter-1',profileName='Test Check-In',start='10:00',end='12:00',date='2026-10-09'))
            before=s.display('SHI','counter-1')
            with self.assertRaises(ValueError):registry.apply(s,dict(airport='SHI',displayId='counter-1',profileName='Test Check-In',start='10:00',end=''))
            self.assertEqual(s.display('SHI','counter-1'),before)
            registry.save_terminal(s,{**terminal,'name':'Renamed'})
            f=s.feed('SHI','counter-1');r.accept('SHI','counter-1',f,f['control'],{image:s.asset('SHI',image)[1]})
            self.assertEqual(ReceiverStore(r.path).display('SHI','counter-1')['signage'],f['control']['signage'])
            registry.apply(s,dict(airport='SHI',displayId='counter-1',profileName=''))
            fallback=s.display('SHI','counter-1')['signage']
            self.assertTrue(fallback['enabled']);self.assertEqual(fallback['start'],'');self.assertEqual(fallback['defaultImage'],image)
            registry.delete_terminal(s,dict(airport='SHI',displayId='counter-1'))
            with s.connect() as db:self.assertFalse(db.execute('SELECT 1 FROM signage_settings').fetchone())
