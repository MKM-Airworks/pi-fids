import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from datetime import datetime,timezone
from pifids import clock_sync
from pifids.store import Store, DraftConflict
from pifids.receiver import ReceiverStore

class ClockTests(unittest.TestCase):
    def test_os_correction_requires_service_and_rejects_stale_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'clock.sqlite');service=Mock()
            data=dict(airport='ROR',mode='set',targetLocal='2026-10-05T12:00:00',expectedRevision=0)
            with self.assertRaises(ValueError):clock_sync.correct_os(store,data,None)
            clock_sync.correct_os(store,data,service)
            service.set_local.assert_called_once_with('2026-10-05T12:00:00')
            self.assertEqual(Store(store.path).clock()['revision'],1)
            self.assertEqual(store.clock()['offsetSeconds'],0)
            with self.assertRaises(DraftConflict):clock_sync.correct_os(store,data,service)
            service.set_local.assert_called_once()
            service.set_local.side_effect=ValueError('Service unavailable')
            with self.assertRaises(ValueError):clock_sync.correct_os(store,{**data,'expectedRevision':1},service)
            self.assertEqual(store.clock()['revision'],1)

    def test_receiver_uses_manager_clock_and_invalid_clock_does_not_replace_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            receiver=ReceiverStore(Path(directory)/'receiver.sqlite')
            control=dict(displayId='board',mode='board',airline='',version=1)
            state=dict(airport='ROR',version=1,flights=[],clock=dict(utcNow='2026-10-05T03:00:00+00:00'))
            with patch('pifids.clock_sync.time.time',return_value=1000):
                receiver.accept('ROR','board',state,control,{})
                self.assertEqual(clock_sync.validate(receiver.clock()),datetime(2026,10,5,3,tzinfo=timezone.utc).timestamp())
                self.assertEqual(receiver.clock()['source'],'management-pc-lan')
                before=receiver.clock()['revision']
                for invalid in ('bad','2026-10-05T12:00:00','2026-10-05T12:00:00+09:00'):
                    with self.assertRaises(ValueError):receiver.accept('ROR','board',{**state,'clock':dict(utcNow=invalid)},control,{})
                self.assertEqual(receiver.clock()['revision'],before)
