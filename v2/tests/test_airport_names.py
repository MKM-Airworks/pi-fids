import tempfile
import unittest
from pathlib import Path
from pifids.store import Store
from pifids.receiver import ReceiverStore

class AirportNameTests(unittest.TestCase):
    def test_names_arrive_and_survive_receiver_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            manager=Store(Path(directory)/'manager.db')
            manager.save_airport_name(dict(airport='SHI',code='ukb',names={'ja':'神戸','en':'Kobe'}))
            feed=manager.feed('SHI','departure-01')
            receiver=ReceiverStore(Path(directory)/'receiver.db')
            receiver.accept('SHI','departure-01',feed,feed['control'],{})
            reopened=ReceiverStore(Path(directory)/'receiver.db')
            self.assertEqual(reopened.read('SHI')['airportNames']['UKB']['en'],'Kobe')
            self.assertEqual(manager.read('ROR')['airportNames']['UKB']['ja'],'神戸')

    def test_invalid_update_and_feed_preserve_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            store=ReceiverStore(Path(directory)/'receiver.db')
            before=store.airport_names('SHI')
            with self.assertRaises(ValueError):store.save_airport_name(dict(airport='SHI',code='HND',names={'en':''}))
            feed=store.feed('SHI','default')
            feed['airportNames']={'BAD':{'en':'x\n'}}
            with self.assertRaises(ValueError):store.accept('SHI','default',feed,feed['control'],{})
            self.assertEqual(store.airport_names('SHI'),before)
