import tempfile
import unittest
from pathlib import Path
from pifids.store import Store, effective_languages, validate


class StoreTests(unittest.TestCase):
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
