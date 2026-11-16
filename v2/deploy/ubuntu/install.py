"""Install a per-user Ubuntu manager or display from its release archive."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PACKAGE = Path(__file__).resolve().parent
sys.path.insert(0, str(PACKAGE / 'v2'))
from pifids import sites
from pifids.security import password_hash, validate_source, write_private
from pifids.store import Store


def validate_manager(args):
    sites.airport_code(args.airport)
    sites.timezone_name(args.timezone)
    address = ipaddress.IPv4Address(args.lan_address)
    if address.is_loopback or address.is_unspecified or address.is_multicast:
        raise ValueError('Select an assigned airport LAN IPv4 address')
    with socket.socket() as probe:
        probe.bind((str(address), 0))


def validate_display(path):
    cfg = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    airport = sites.airport_code(cfg['airport'])
    display = cfg['displayId']
    Store.validate_display_id(display)
    sites.timezone_name(cfg.get('timezone', sites.DEFAULT_ZONES.get(airport, 'UTC')))
    source = validate_source(cfg['source'])
    token = cfg['token']
    if not isinstance(token, str) or not 32 <= len(token) <= 128 or not token.isascii() or any(c.isspace() for c in token):
        raise ValueError('Invalid terminal credential')
    url = source + '/api/feed?' + urlencode({'airport':airport, 'displayId':display})
    from pifids.receiver import NoRedirect
    from urllib.request import build_opener
    with build_opener(NoRedirect()).open(Request(url,headers={'Authorization':'Bearer '+token}), timeout=15) as response:
        feed = json.load(response)
    if feed.get('airport') != airport or feed.get('control', {}).get('displayId') != display:
        raise ValueError('Connection file does not match the feed identity')
    return cfg


def main():
    role = (PACKAGE / 'ROLE').read_text().strip()
    parser = argparse.ArgumentParser(description=f'Pi-FIDS Ubuntu {role} setup')
    if role == 'manager':
        parser.add_argument('--airport', required=True)
        parser.add_argument('--timezone', required=True)
        parser.add_argument('--lan-address', required=True)
    else:
        parser.add_argument('--connection', required=True)
    args = parser.parse_args()
    if sys.platform != 'linux' or os.geteuid() == 0:
        parser.error('Run on Ubuntu as the account that will operate Pi-FIDS, without sudo')
    try:
        if role == 'manager':
            validate_manager(args)
        else:
            connection = validate_display(args.connection)
            if not any(shutil.which(name) for name in ('chromium','chromium-browser','google-chrome','microsoft-edge')):
                parser.error('Install a supported kiosk browser before setting up the display')
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.error(str(error))
    root = Path.home() / '.local/share' / ('pi-fids-' + role)
    unit_name = 'pi-fids-' + role + '.service'
    config_root = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    unit = config_root / 'systemd/user' / unit_name
    desktop = config_root / 'autostart/pi-fids-display.desktop'
    if root.exists() or unit.exists() or (role == 'display' and desktop.exists()):
        parser.error('Existing installation found. Its data and configuration have been preserved.')
    subprocess.run(['systemctl','--user','show-environment'], check=True, stdout=subprocess.DEVNULL)

    root.mkdir(parents=True, mode=0o700)
    data = root / 'data'
    data.mkdir(mode=0o700)
    shutil.copytree(PACKAGE / 'v2', root / 'v2')
    shutil.copy2(PACKAGE / 'launch.py', root)
    if role == 'manager':
        shutil.copytree(PACKAGE / 'downloads', root / 'downloads')
        write_private(data/'site.json', dict(airport=args.airport,timezone=args.timezone,lanAddress=args.lan_address))
        salt = secrets.token_hex(16)
        write_private(data/'lan-auth.json',dict(airport=args.airport,timezone=args.timezone,
                      username='unused-lan-only',salt=salt,passwordHash=password_hash(secrets.token_urlsafe(48),salt),terminals={}))
        action = 'manager'
    else:
        write_private(data/'connection.json', connection)
        desktop.parent.mkdir(parents=True, exist_ok=True)
        desktop.write_text('[Desktop Entry]\nType=Application\nName=Pi-FIDS Kiosk\n'
                           f'Exec=/usr/bin/python3 "{root}/launch.py" kiosk\n',encoding='utf-8')
        action = 'receiver'
    unit.parent.mkdir(parents=True, exist_ok=True)
    unit.write_text('[Unit]\nDescription=Pi-FIDS V2 '+role+'\n\n[Service]\n'
                    f'ExecStart=/usr/bin/python3 "%h/.local/share/pi-fids-{role}/launch.py" {action}\n'
                    'Restart=on-failure\nRestartSec=3\nUMask=0077\n\n[Install]\nWantedBy=default.target\n',
                    encoding='utf-8')
    subprocess.run(['systemctl','--user','daemon-reload'], check=True)
    subprocess.run(['systemctl','--user','enable','--now',unit_name], check=True)
    print('Installed / インストール完了')
    if role == 'manager':
        print('Manager: http://127.0.0.1:8800/')
        print(f'Display downloads: http://{args.lan_address}:8805/downloads')
    else:
        print(f'Start kiosk now: /usr/bin/python3 "{root}/launch.py" kiosk')


if __name__ == '__main__':
    main()
