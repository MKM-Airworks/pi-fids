import tempfile
import unittest
from pathlib import Path
from pifids.store import Store, validate
from pifids.receiver import ReceiverStore

class BoardTimingTests(unittest.TestCase):
    def test_dates_actual_and_validation(self):
        base=dict(airport='ROR',flightNumber='BC101',destination='Tokyo',time='23:55',serviceDate='2026-10-05',estimatedTime='00:15',estimatedDate='2026-10-06',actualTime='00:20',actualDate='2026-10-06')
        self.assertEqual(validate(base)['actualDate'],'2026-10-06')
        for patch in ({'serviceDate':'2026-02-30'},{'actualTime':'24:00'},{'actualDate':'2026-10-7'},{'actualTime':''},{'estimatedTime':''}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):validate({**base,**patch})

    def test_feed_receiver_restart_retains_policy_and_operational_dates(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Store(Path(directory)/'source.sqlite');receiver=ReceiverStore(Path(directory)/'receiver.sqlite')
            source.add(dict(airport='ROR',flightNumber='BC102',destination='Tokyo',time='23:55',direction='arrival',serviceDate='2026-10-05',actualTime='00:20',actualDate='2026-10-06'))
            source.publish('ROR');source.set_display(dict(airport='ROR',displayId='board',mode='board',departureHideMinutes=25,arrivalHideMinutes=90))
            feed=source.feed('ROR','board');receiver.accept('ROR','board',feed,feed['control'],{})
            restored=ReceiverStore(Path(directory)/'receiver.sqlite')
            self.assertEqual(restored.display('ROR','board')['arrivalHideMinutes'],90)
            self.assertEqual(restored.display('ROR','board')['departureHideMinutes'],25)
            self.assertEqual(restored.read('ROR')['flights'][0]['actualDate'],'2026-10-06')
            self.assertEqual(source.read('ROR')['flights'][0]['actualTime'],'00:20')
            self.assertEqual(source.display('ROR','other')['arrivalHideMinutes'],120)
            for value in (True,-1,1.5,'10',10081):
                with self.subTest(value=value),self.assertRaises(ValueError):
                    source.set_display(dict(airport='ROR',displayId='board',mode='board',departureHideMinutes=value))
            self.assertEqual(source.display('ROR','board')['departureHideMinutes'],25)
