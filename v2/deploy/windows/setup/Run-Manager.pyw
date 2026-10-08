"""Run the installation manager and separate read-only LAN feed."""
import json
import os
from pathlib import Path
import runpy
import sys
root = Path(os.environ['LOCALAPPDATA']) / 'MKM' / 'PiFidsManager'
site = json.loads((root / 'data' / 'site.json').read_text(encoding='utf-8-sig'))
sys.stdout = (root / 'manager.log').open('a', buffering=1, encoding='utf-8')
sys.stderr = (root / 'manager-error.log').open('a', buffering=1, encoding='utf-8')
sys.argv = ['pifids', '--database', str(root / 'data' / 'manager.sqlite'),
            '--site-config', str(root / 'data' / 'site.json'),
            '--feed-config', str(root / 'data' / 'lan-auth.json'),
            '--port', '8800', '--lan-port', '8805', '--lan-host', site['lanAddress']]
if (root / 'data' / 'web-connection.json').exists():
    sys.argv += ['--upstream-config', str(root / 'data' / 'web-connection.json')]
runpy.run_module('pifids', run_name='__main__')
