import tempfile
import unittest
from pathlib import Path
from pifids.store import Store
from pifids.receiver import ReceiverStore
from pifids import sites

class SiteTests(unittest.TestCase):
    def test_new_airport_flows_to_receiver_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Store(Path(directory)/'manager.sqlite')
            source.configure_site('BKK','Asia/Bangkok')
            source.add(dict(airport='BKK',flightNumber='TG101',destination='HND',time='10:00',serviceDate='2026-10-08'))
            source.publish('BKK')
            feed=source.feed('BKK','gate-02')
            self.assertEqual(feed['timezone'],'Asia/Bangkok')
            receiver=ReceiverStore(Path(directory)/'receiver.sqlite')
            receiver.accept('BKK','gate-02',feed,feed['control'],{})
            restored=ReceiverStore(receiver.path)
            self.assertEqual(restored.read('BKK')['flights'][0]['flightNumber'],'TG101')
            self.assertEqual(restored.read('BKK')['timezone'],'Asia/Bangkok')
            with self.assertRaises(ValueError):restored.configure_site('BKK','UTC')
            with self.assertRaises(ValueError):source.read('LHR')

    def test_bad_airport_or_timezone_is_rejected(self):
        for code in ('../','shi','AB','ABCD',None):
            with self.assertRaises(ValueError):sites.airport_code(code)
        with self.assertRaises(ValueError):sites.timezone_name('Unknown/Zone')
