"""Initialize a new installation; never export manager-wide credentials."""
import argparse
import secrets
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent/'v2'))
from pifids.store import Store
from pifids.security import write_private, password_hash
from pifids import sites
parser=argparse.ArgumentParser()
parser.add_argument('--root', required=True)
parser.add_argument('--airport',type=sites.airport_code, required=True)
parser.add_argument('--timezone',type=sites.timezone_name, required=True)
parser.add_argument('--lan-address',required=True)
parser.add_argument('--check-only',action='store_true')
args=parser.parse_args()
if args.check_only:
    print('Airport and timezone verified')
else:
    root=Path(args.root)
    data=root/'data'
    data.mkdir(parents=True,exist_ok=True)
    Store(data/'manager.sqlite').configure_site(args.airport,args.timezone)
    write_private(data/'site.json',dict(airport=args.airport,timezone=args.timezone,lanAddress=args.lan_address),exclusive=True)
    salt=secrets.token_hex(16)
    write_private(data/'lan-auth.json',dict(airport=args.airport,timezone=args.timezone,username='unused-lan-only',salt=salt,passwordHash=password_hash(secrets.token_urlsafe(48),salt),terminals={}),exclusive=True)
    print('Installation initialized')
