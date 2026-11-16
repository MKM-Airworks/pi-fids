"""Launch an installed Pi-FIDS manager, receiver, or desktop kiosk."""
import json
import os
from pathlib import Path
import shutil
import sys
import time
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'


def config(name):
    return json.loads((DATA / name).read_text(encoding='utf-8-sig'))


def app(module, args):
    os.chdir(ROOT / 'v2')
    os.execv(sys.executable, [sys.executable, '-m', module, *map(str, args)])


def manager():
    site = config('site.json')
    lan = site['lanAddress']
    args = ['--database', DATA / 'manager.sqlite', '--site-config', DATA / 'site.json',
            '--auth-config', DATA / 'lan-auth.json', '--port', '8800',
            '--lan-host', lan, '--lan-port', '8805', '--terminal-source', f'http://{lan}:8805',
            '--download-directory', ROOT / 'downloads']
    upstream = DATA / 'web-connection.json'
    if upstream.is_file():
        args.extend(['--upstream-config', upstream])
    app('pifids', args)


def receiver():
    app('pifids.receiver', ['--connection', DATA / 'connection.json',
                           '--database', DATA / 'receiver.sqlite', '--port', '8801'])


def kiosk():
    connection = config('connection.json')
    query = urlencode({'airport':connection['airport'], 'displayId':connection['displayId'], 'kiosk':'1'})
    url = 'http://127.0.0.1:8801/display?' + query
    for _ in range(90):
        try:
            with urlopen(url, timeout=2) as response:
                if response.status == 200:
                    break
        except OSError:
            time.sleep(1)
    else:
        raise SystemExit('Pi-FIDS receiver unavailable on localhost:8801')
    for name in ('chromium', 'chromium-browser', 'google-chrome', 'microsoft-edge'):
        browser = shutil.which(name)
        if browser:
            break
    else:
        raise SystemExit('Install Chromium, Chrome or Edge before running Pi-FIDS Kiosk')
    profile = (Path.home() / 'snap/chromium/common/pi-fids-kiosk'
               if name.startswith('chromium') else ROOT / 'browser-profile')
    os.execv(browser,[browser,'--kiosk','--no-first-run',f'--user-data-dir={profile}',url])


if __name__ == '__main__':
    {'manager':manager, 'receiver':receiver, 'kiosk':kiosk}[sys.argv[1]]()
