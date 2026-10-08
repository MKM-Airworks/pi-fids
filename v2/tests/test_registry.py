import tempfile
import unittest
from pathlib import Path
from pifids.store import Store
from pifids import registry
from test_assets import png
import base64

class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=Store(Path(self.temp.name)/'manager.sqlite')
        self.terminal=dict(airport='ROR',displayId='counter-01',name='Check-in Counter 01',departureHideMinutes=25,arrivalHideMinutes=90)
        self.profile=dict(airport='ROR',name='JX Business Class',mode='counter',airline='STARLUX Airlines',logo='',image='')
    def test_named_registration_apply_and_restart(self):
        registry.save_terminal(self.store,self.terminal)
        digest=self.store.upload_asset(dict(airport='ROR',name='JX Business Class artwork',body=base64.b64encode(png()).decode()))
        registry.save_profile(self.store,{**self.profile,'image':digest})
        registry.apply(self.store,dict(airport='ROR',displayId='counter-01',profileName='JX Business Class'))
        restored=Store(self.store.path);result=registry.listing(restored,'ROR')
        self.assertEqual(result['terminals'][0]['name'],'Check-in Counter 01')
        self.assertEqual(result['terminals'][0]['profileName'],'JX Business Class')
        self.assertEqual(result['profiles'][0]['name'],'JX Business Class')
        feed=restored.feed('ROR','counter-01')['control']
        self.assertEqual(feed['image'],digest);self.assertEqual(feed['mode'],'counter');self.assertEqual(feed['departureHideMinutes'],25)
        registry.save_terminal(restored,{**self.terminal,'name':'Counter A','arrivalHideMinutes':180})
        self.assertEqual(restored.display('ROR','counter-01')['image'],digest)
        registry.apply(restored,dict(airport='ROR',displayId='counter-01',profileName=''))
        self.assertEqual(restored.display('ROR','counter-01')['mode'],'board')
        self.assertEqual(restored.display('ROR','counter-01')['arrivalHideMinutes'],180)
    def test_scope_validation_and_atomic_duplicate_rejection(self):
        registry.save_terminal(self.store,self.terminal);registry.save_profile(self.store,self.profile)
        for data in ({**self.terminal,'displayId':'counter-02'}, {**self.terminal,'name':''},{**self.terminal,'departureHideMinutes':-1}):
            with self.assertRaises(ValueError):registry.save_terminal(self.store,data)
        self.assertEqual(len(registry.listing(self.store,'ROR')['terminals']),1)
        self.assertEqual(registry.listing(self.store,'SHI'),dict(terminals=[],profiles=[]))
        registry.save_terminal(self.store,{**self.terminal,'airport':'SHI'})
        for data in (dict(airport='SHI',displayId='counter-01',profileName=self.profile['name']),dict(airport='ROR',displayId='missing',profileName=self.profile['name'])):
            with self.assertRaises(ValueError):registry.apply(self.store,data)
        self.assertEqual(self.store.display('ROR','counter-01')['mode'],'board')
        for patch in ({'mode':'board'},{'image':'0'*64},{'airline':''},{'name':''}):
            with self.assertRaises(ValueError):registry.save_profile(self.store,{**self.profile,**patch})
    def test_profile_edit_does_not_implicitly_switch_screen(self):
        registry.save_terminal(self.store,self.terminal);registry.save_profile(self.store,self.profile)
        registry.apply(self.store,dict(airport='ROR',displayId='counter-01',profileName=self.profile['name']))
        before=self.store.display('ROR','counter-01')
        registry.save_profile(self.store,{**self.profile,'mode':'gate'})
        self.assertEqual(self.store.display('ROR','counter-01'),before)
        registry.apply(self.store,dict(airport='ROR',displayId='counter-01',profileName=self.profile['name']))
        self.assertEqual(self.store.display('ROR','counter-01')['mode'],'gate')
    def test_legacy_terminals_migrate_without_changing_display(self):
        self.store.set_display(dict(airport='ROR',displayId='gate-02',mode='gate',airline='Sample'))
        before=self.store.display('ROR','gate-02')
        self.assertEqual(registry.listing(self.store,'ROR')['terminals'],[dict(displayId='gate-02',name='gate-02',profileName=None,usage='signage',direction='departure',currentDisplay='Sample')])
        self.assertEqual(self.store.display('ROR','gate-02'),before)

    def test_same_image_choices_keep_the_selected_name(self):
        registry.save_terminal(self.store,self.terminal)
        registry.save_profile(self.store,self.profile)
        registry.save_profile(self.store,{**self.profile,'name':'JX Economy Class'})
        registry.apply(self.store,dict(airport='ROR',displayId='counter-01',profileName='JX Economy Class'))
        self.assertEqual(registry.listing(self.store,'ROR')['terminals'][0]['profileName'],'JX Economy Class')
        self.store.set_display(dict(airport='ROR',displayId='counter-01',mode='gate',airline='Other airline'))
        self.assertIsNone(registry.listing(self.store,'ROR')['terminals'][0]['profileName'])

class TerminalDeletionTests(unittest.TestCase):
    def test_delete_preserves_profiles_and_blocks_feed_until_reregistered(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'test.sqlite')
            registry.save_terminal(store,dict(airport='SHI',displayId='test-01',name='Test',usage='signage'))
            registry.save_profile(store,dict(airport='SHI',name='ANA Business',mode='counter',airline='ANA',logo='',image=''))
            registry.apply(store,dict(airport='SHI',displayId='test-01',profileName='ANA Business'))
            registry.delete_terminal(store,dict(airport='SHI',displayId='test-01'))
            self.assertEqual(registry.listing(store,'SHI')['terminals'],[])
            self.assertEqual(len(registry.listing(store,'SHI')['profiles']),1)
            with self.assertRaises(ValueError):store.feed('SHI','test-01')
            registry.save_terminal(store,dict(airport='SHI',displayId='test-01',name='Test',usage='board'))
            self.assertEqual(store.feed('SHI','test-01')['control']['mode'],'board')
