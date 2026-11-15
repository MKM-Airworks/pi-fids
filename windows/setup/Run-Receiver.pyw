"""Run the local receiver without a console; logs stay on this terminal."""
import os
from pathlib import Path
import runpy
import sys
root = Path(os.environ['LOCALAPPDATA']) / 'MKM' / 'PiFidsDisplay'
sys.stdout = (root / 'receiver.log').open('a', buffering=1, encoding='utf-8')
sys.stderr = (root / 'receiver-error.log').open('a', buffering=1, encoding='utf-8')
sys.argv = ['pifids.receiver', '--connection', str(root / 'data' / 'connection.json'),
            '--database', str(root / 'data' / 'receiver.sqlite'), '--port', '8801']
runpy.run_module('pifids.receiver', run_name='__main__')
