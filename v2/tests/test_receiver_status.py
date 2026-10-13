import unittest,tempfile
from pathlib import Path
from unittest.mock import patch
from pifids.receiver import ReceiverStore
class StatusTests(unittest.TestCase):
 def test_start_failure_expiry_recovery(self):
  with tempfile.TemporaryDirectory() as d:
   s=ReceiverStore(Path(d)/'db');self.assertFalse(s.connection_status()['online'])
   s.last_sync_monotonic=100
   with patch('pifids.receiver.time.monotonic',return_value=119):self.assertTrue(s.connection_status()['online'])
   with patch('pifids.receiver.time.monotonic',return_value=120):self.assertFalse(s.connection_status()['online'])
   s.sync_failed=True
   with patch('pifids.receiver.time.monotonic',return_value=101):self.assertFalse(s.connection_status()['online']);s.sync_failed=False;self.assertTrue(s.connection_status()['online'])
