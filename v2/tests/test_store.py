import tempfile
import unittest
from pathlib import Path
from pifids.store import Store, effective_languages, validate


class StoreTests(unittest.TestCase):
    def test_display_switch_isolated_persistent_and_restorable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'data.sqlite'
            store = Store(path)
            store.set_display({'airport':'ROR', 'displayId':'gate-01', 'mode':'gate', 'airline':'Sample Air'})
            self.assertEqual(Store(path).display('ROR', 'gate-01')['airline'], 'Sample Air')
            self.assertEqual(store.display('SHI', 'gate-01')['mode'], 'board')
            self.assertEqual(store.display('ROR', 'gate-02')['mode'], 'board')
            store.set_display({'airport':'ROR', 'displayId':'gate-01', 'mode':'board', 'airline':'Sample Air'})
            self.assertEqual(store.display('ROR', 'gate-01'), {'logo':'', 'image':'', 'displayId':'gate-01', 'mode':'board', 'airline':'', 'version':2})

    def test_invalid_display_instruction_does_not_replace_current(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'data.sqlite')
            base = {'airport':'ROR', 'displayId':'gate-01', 'mode':'gate', 'airline':'Sample Air'}
            store.set_display(base)
            for patch in ({'airport':'XXX'}, {'displayId':'../bad'}, {'mode':'unknown'}, {'airline':''}):
                with self.assertRaises(ValueError):
                    store.set_display({**base, **patch})
            self.assertEqual(store.display('ROR', 'gate-01')['version'], 1)

    def test_draft_isolated_until_publish_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'data.sqlite'
            store = Store(path)
            store.add({'airport':'ROR','flightNumber':'UA158','destination':'Guam','time':'23:30','languages':['ko','en']})
            self.assertEqual(store.read('ROR')['flights'], [])
            self.assertEqual(store.read('SHI')['draft'], [])
            store.publish('ROR')
            restored = Store(path).read('ROR')
            self.assertEqual(restored['version'], 1)
            self.assertEqual(restored['flights'][0]['languages'], ['ko','en'])

    def test_invalid_languages_and_time_rejected(self):
        base = {'airport':'SHI','flightNumber':'BC101','destination':'Tokyo','time':'10:00'}
        for patch in ({'languages':['en','en']},{'languages':['xx']},{'time':'24:00'},{'airport':'XXX'}):
            with self.assertRaises(ValueError):
                validate({**base, **patch})

    def test_unset_languages_inherit_defaults(self):
        self.assertEqual(effective_languages({'languages':[]}, ['ja','en']), ['ja','en'])
        self.assertEqual(effective_languages({'languages':['ko','en']}, ['ja']), ['ko','en'])


if __name__ == '__main__':
    unittest.main()
