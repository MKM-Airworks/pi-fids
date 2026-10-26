"""Windows PowerShell 5.1 integration test; no live receiver/browser is changed."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse


@unittest.skipUnless(os.name == 'nt', 'requires Windows PowerShell and Windows mutexes')
class DisplayStartupTest(unittest.TestCase):
    def test_slow_receiver_identity_offline_cache_and_single_worker(self):
        launcher = Path(os.environ.get('PIFIDS_STARTUP_LAUNCHER',
            Path(__file__).resolve().parents[2] / 'deploy/windows/setup/Open-Display.ps1'))
        phase = {'value': 'unavailable'}
        seen = set()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                current = phase['value']
                path = urlparse(self.path).path
                seen.add((current, path))
                if current == 'unavailable':
                    self.send_error(503)
                    return
                body = ({'airport': 'SHI' if current == 'wrong-airport' else 'ROR',
                         'flights': [], 'online': False} if path == '/api/state' else
                        {'displayId': 'wrong' if current == 'wrong-terminal' else 'test-display'})
                data = json.dumps(body).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        worker = duplicate = None
        try:
            with tempfile.TemporaryDirectory(prefix='pifids-startup-test-') as root:
                data = Path(root) / 'data'
                data.mkdir()
                (data / 'connection.json').write_text(json.dumps(
                    {'airport': 'ROR', 'displayId': 'test-display'}), encoding='utf-8')
                cmd = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                       '-File', str(launcher), '-Root', root, '-Port', str(server.server_port),
                       '-PollSeconds', '1', '-CheckOnly']
                worker = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                def wait_seen(value, path):
                    deadline = time.monotonic() + 120
                    while (value, path) not in seen and time.monotonic() < deadline:
                        self.assertIsNone(worker.poll(), 'worker exited before receiver became ready')
                        time.sleep(0.1)
                    self.assertIn((value, path), seen)

                wait_seen('unavailable', '/api/state')
                # A simultaneous shortcut/task invocation must not create a second waiter.
                duplicate = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                duplicate.communicate(timeout=120)
                self.assertEqual(duplicate.returncode, 0)
                self.assertIsNone(worker.poll())
                for value, endpoint in [('wrong-airport', '/api/state'),
                                        ('wrong-terminal', '/api/display')]:
                    phase['value'] = value
                    wait_seen(value, endpoint)
                    time.sleep(1.5)
                    self.assertIsNone(worker.poll(), 'accepted the wrong receiver identity')
                phase['value'] = 'offline-cache-ready'
                stdout, stderr = worker.communicate(timeout=120)
                self.assertEqual(worker.returncode, 0, stderr.decode(errors='replace'))
                log = (Path(root) / 'display-startup.log').read_text(encoding='utf-8-sig')
                self.assertIn('Receiver is not ready; retrying', log)
                self.assertIn('Readiness check passed', log)
                self.assertEqual(log.count('Startup worker started'), 1)
        finally:
            for process in (worker, duplicate):
                if process and process.poll() is None:
                    process.kill()
                    process.communicate()
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
