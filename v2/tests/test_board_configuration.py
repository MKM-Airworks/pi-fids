import base64
import tempfile
import unittest
from pathlib import Path
from pifids.store import Store
from pifids.receiver import ReceiverStore
from pifids import registry, board_config
from test_assets import png

class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=Store(Path(self.temp.name)/'manager.sqlite')
    def test_separate_departure_arrival_columns_receiver_and_purpose(self):
        logo=self.store.upload_asset(dict(airport='ROR',name='Airport logo',body=base64.b64encode(png()).decode(),kind='logo'))
        board=dict(languages=['en','ja','zh-Hans'],languageInterval=10,direction='arrival',departureColumns=['scheduled','flight'],arrivalColumns=['destination','flight','remark'],logo=logo)
        registry.save_terminal(self.store,dict(airport='ROR',displayId='arrivals-01',name='Arrival lobby',usage='board',board=board,arrivalHideMinutes=180))
        control=self.store.display('ROR','arrivals-01');self.assertEqual(control['board'],board);self.assertEqual(control['mode'],'board')
        registry.save_profile(self.store,dict(airport='ROR',name='JX Business',mode='counter',airline='STARLUX'))
        with self.assertRaises(ValueError):registry.apply(self.store,dict(airport='ROR',displayId='arrivals-01',profileName='JX Business'))
        receiver=ReceiverStore(Path(self.temp.name)/'receiver.sqlite');feed=self.store.feed('ROR','arrivals-01')
        receiver.accept('ROR','arrivals-01',feed,feed['control'],{logo:png()})
        restored=ReceiverStore(receiver.path)
        self.assertEqual(restored.display('ROR','arrivals-01')['board'],board);self.assertEqual(restored.asset('ROR',logo)[1],png())
        for patch in ({'direction':'both'},{'departureColumns':[]},{'arrivalColumns':['secret']},{'arrivalColumns':['flight','flight']},{'languages':[]},{'languages':['en','en']},{'languages':['xx']},{'languageInterval':2},{'languageInterval':True}):
            with self.assertRaises(ValueError):board_config.validate({**board,**patch})
        registry.save_terminal(self.store,dict(airport='ROR',displayId='gate-01',name='Gate 01',usage='signage'))
        registry.apply(self.store,dict(airport='ROR',displayId='gate-01',profileName='JX Business'))
        self.assertEqual(self.store.display('ROR','gate-01')['mode'],'counter')
    def test_image_categories_and_size(self):
        full=png()[:16]+(1920).to_bytes(4,'big')+(1080).to_bytes(4,'big')+png()[24:]
        image=self.store.upload_asset(dict(airport='ROR',name='JX Business',kind='signage',body=base64.b64encode(full).decode()))
        self.assertEqual(self.store.assets('ROR')[0]['kind'],'signage')
        with self.assertRaises(ValueError):self.store.upload_asset(dict(airport='ROR',name='Wrong size',kind='signage',body=base64.b64encode(png()).decode()))
        logo=self.store.upload_asset(dict(airport='ROR',name='JX Logo',kind='logo',body=base64.b64encode(png()).decode()))
        with self.assertRaises(ValueError):registry.save_profile(self.store,dict(airport='ROR',name='Logo as artwork',mode='gate',airline='JX',image=logo))
        registry.save_profile(self.store,dict(airport='ROR',name='JX Business',mode='counter',airline='JX',image=image))
        self.assertEqual(len(self.store.assets('ROR')),2)

    def test_legacy_settings_get_terminal_defaults(self):
        config=board_config.validate({'direction':'departure'})
        self.assertEqual(config['languages'],['en','ja'])
        self.assertEqual(config['languageInterval'],8)
