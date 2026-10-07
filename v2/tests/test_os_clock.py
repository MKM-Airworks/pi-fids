import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pifids.os_clock import OsClock, WindowsClockStatus

class OsClockTests(unittest.TestCase):
    def test_windows_status_does_not_allow_clock_writes(self):
        clock=WindowsClockStatus()
        with patch.dict('os.environ', {'SystemRoot':'C:/Windows'}), patch('pifids.os_clock.subprocess.run') as run:
            run.return_value.stdout='{"serviceStatus":"Running","ntpServerEnabled":true}'
            self.assertTrue(clock.status()['ntpServerEnabled'])
            self.assertFalse(clock.can_set)
            with self.assertRaises(ValueError):clock.set_local('2026-10-07T12:00:00')
            self.assertEqual(run.call_count,1)
    def test_loopback_auth_and_time_conversion_without_changing_os(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'clock.json';path.write_text(json.dumps(dict(baseUrl='http://127.0.0.1:8816',token='synthetic-clock-key-only-1234567890')))
            clock=OsClock(path)
            class Response:
                def __enter__(self):return self
                def __exit__(self,*args):return False
                def read(self,limit):return b'{"serviceStatus":"Running"}'
            with patch('pifids.os_clock.build_opener') as opener:
                opener.return_value.open.return_value=Response()
                clock.set_local('2026-10-05T12:00:00')
                request=opener.return_value.open.call_args.args[0]
                self.assertEqual(request.full_url,'http://127.0.0.1:8816/set')
                self.assertEqual(json.loads(request.data),{'utcNow':'2026-10-05T03:00:00+00:00'})
                self.assertTrue(request.get_header('Authorization').startswith('Bearer '))
            for base in ('http://192.168.1.1:8816','http://user@127.0.0.1:8816','http://127.0.0.1:8816/other'):
                path.write_text(json.dumps(dict(baseUrl=base,token='synthetic-clock-key-only-1234567890')))
                with self.assertRaises(ValueError):clock.status()
            for bad in ('bad','2026-10-05T03:00:00+00:00'):
                with self.assertRaises(ValueError):clock.set_local(bad)
    def test_os_clock_changes_require_manager_login_configuration(self):
        import subprocess
        import sys
        result=subprocess.run([sys.executable,'-m','pifids','--clock-service','not-a-real-clock-config.json'],capture_output=True,text=True)
        self.assertEqual(result.returncode,2)
        self.assertIn('requires manager authentication',result.stderr)
