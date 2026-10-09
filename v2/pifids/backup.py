"""Consistent manager snapshots and isolated, offline recovery preparation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import threading
import uuid
import zipfile
from datetime import datetime, timezone
from .store import Store, ClosingConnection
from . import registry, sites

FORMAT = 'pifids-manager-backup/1'
MAX_BYTES = 128 * 1024 * 1024
FILES = {'manager.sqlite', 'manager-auth.json', 'manager-auth.users.json', 'web-connection.template.json', 'site.json'}

def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode('utf-8')

def digest(body):
    return hashlib.sha256(body).hexdigest()

def private(path, body):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as file:
        file.write(body)

def schema(db):
    return {row[0]: row[1] for row in db.execute("SELECT name,sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'")}

def expected_schema(directory):
    # Build the current schema using the same initializers, never archive SQL.
    from .upstream import init_tables
    store = Store(Path(directory) / 'expected.sqlite')
    with store.connect() as db:required=set(schema(db))
    registry.init(store)
    init_tables(store)
    with store.connect() as db:
        return schema(db),required

def validate_database(path, directory, airport):
    expected, required = expected_schema(directory)
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, factory=ClosingConnection) as db:
        db.execute('PRAGMA trusted_schema=OFF')
        if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise ValueError('Database integrity check failed')
        actual = schema(db)
        if any(name not in expected or sql != expected[name] for name, sql in actual.items()):
            raise ValueError('Unsupported database schema')
        if not required.issubset(actual):
            raise ValueError('Incomplete database')
        row = db.execute('SELECT timezone FROM site_settings WHERE airport=?', (airport,)).fetchone()
        if not row:
            raise ValueError('Backup airport is missing')
        sites.timezone_name(row[0])
        assets = {}
        for a, d, mime, body in db.execute('SELECT airport,digest,mime,body FROM assets'):
            if digest(body) != d or mime not in ('image/png', 'image/jpeg'):
                raise ValueError('Image integrity check failed')
            assets.setdefault(a, set()).add(d)
        def reference(a, d):
            if d and d not in assets.get(a, set()):
                raise ValueError('Referenced image is missing')
        flights = terminals = 0
        for a, draft, published in db.execute('SELECT airport,draft,published FROM state'):
            for raw in (draft, published):
                items = json.loads(raw)
                if not isinstance(items, list):raise ValueError('Invalid flight data')
                for flight in items:
                    if not isinstance(flight, dict):raise ValueError('Invalid flight data')
                    from .store import validate
                    zone=db.execute('SELECT timezone FROM site_settings WHERE airport=?',(a,)).fetchone()
                    if not zone:raise ValueError('Flight airport is missing')
                    validate(flight,zone[0])
                    reference(a, flight.get('airlineLogo', ''))
            if a == airport:flights = len(json.loads(published))
        if 'display_assets' in actual:
            for a, logo, image in db.execute('SELECT airport,logo,image FROM display_assets'):
                reference(a, logo); reference(a, image)
        if 'signage_settings' in actual:
            for a, body in db.execute('SELECT airport,body FROM signage_settings'):
                from .signage_config import validate
                reference(a, validate(json.loads(body))['defaultImage'])
        if 'board_settings' in actual:
            for a, body in db.execute('SELECT airport,body FROM board_settings'):
                from .board_config import validate
                reference(a, validate(json.loads(body))['logo'])
        if 'airline_names' in actual:
            for a, body in db.execute('SELECT airport,body FROM airline_names'):
                for item in json.loads(body).values():reference(a, item.get('logo', ''))
        if 'signage_profiles' in actual:
            for a, logo, image in db.execute('SELECT airport,logo,image FROM signage_profiles'):
                reference(a, logo);reference(a, image)
        terminals = db.execute('SELECT count(*) FROM displays WHERE airport=?', (airport,)).fetchone()[0]
        return {'flights': flights, 'images': len(assets.get(airport, set())), 'terminals': terminals, 'timezone':row[0]}

def validate_auth(auth, users, airport):
    if not isinstance(auth, dict) or set(auth) - {'airport','timezone','username','salt','passwordHash','terminals'} or auth.get('airport') != airport:
        raise ValueError('Invalid authentication backup')
    sites.timezone_name(auth.get('timezone'))
    if not isinstance(auth.get('terminals'),dict) or not isinstance(users,dict):raise ValueError('Invalid users')
    for name, token_hash in auth['terminals'].items():
        Store.validate_display_id(name)
        if not isinstance(token_hash,str) or not re.fullmatch('[a-f0-9]{64}',token_hash):raise ValueError('Invalid terminal key hash')
    for user in [auth, *users.values()]:
        for key, length in [('salt',32),('passwordHash',64)]:
            if not isinstance(user.get(key),str) or not re.fullmatch('[a-f0-9]{'+str(length)+'}',user[key]):raise ValueError('Invalid password hash')
    for name, user in users.items():
        if not re.fullmatch(r'[A-Za-z0-9_.@-]{1,100}',name) or set(user) != {'salt','passwordHash','role','active'} or user['role'] not in ('admin','operator') or type(user['active']) is not bool:raise ValueError('Invalid user settings')
    if not any(u['role']=='admin' and u['active'] for u in users.values()):raise ValueError('Backup needs an active administrator')

def inspect_archive(archive_path, airport, target=None):
    """Validate completely before atomically publishing a NEW recovery folder."""
    airport = sites.airport_code(airport)
    archive_path = Path(archive_path)
    if archive_path.stat().st_size > MAX_BYTES:raise ValueError('Backup is too large')
    target = Path(target).resolve() if target else None
    if target and target.exists():raise ValueError('Recovery folder already exists; live data cannot be overwritten')
    if target:target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent if target else None) as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(archive_path) as archive:
            entries = archive.infolist()
            names = [e.filename for e in entries]
            if len(names) != len(set(names)) or set(names) - (FILES | {'manifest.json'}) or 'manifest.json' not in names or sum(e.file_size for e in entries) > MAX_BYTES:
                raise ValueError('Invalid backup entries or size')
            if any(e.is_dir() or e.flag_bits & 1 or ((e.external_attr >> 16) & 0o170000) == 0o120000 for e in entries):raise ValueError('Invalid backup entry')
            manifest = json.loads(archive.read('manifest.json'))
            created = datetime.fromisoformat(manifest['createdAt'])
            if created.tzinfo is None:raise ValueError('Backup timestamp needs a timezone')
            if manifest.get('format') != FORMAT or manifest.get('airport') != airport:raise ValueError('Backup format or airport mismatch')
            inventory = manifest.get('files')
            if not isinstance(inventory,dict) or set(inventory) != set(names)-{'manifest.json'} or not {'manager.sqlite','manager-auth.json','manager-auth.users.json','site.json'}.issubset(inventory):raise ValueError('Incomplete backup inventory')
            for name, meta in inventory.items():
                body = archive.read(name)
                if meta != {'bytes':len(body),'sha256':digest(body)}:raise ValueError('Backup checksum mismatch')
                private(root / name, body)
        auth = json.loads((root/'manager-auth.json').read_bytes())
        users = json.loads((root/'manager-auth.users.json').read_bytes())
        validate_auth(auth, users, airport)
        summary = validate_database(root/'manager.sqlite', root, airport)
        site = json.loads((root/'site.json').read_bytes())
        if site != {'airport':airport,'timezone':summary['timezone']}:raise ValueError('Invalid site configuration')
        if auth['timezone'] != site['timezone']:raise ValueError('Timezone mismatch')
        template = root/'web-connection.template.json'
        if template.exists():
            value=json.loads(template.read_bytes())
            if set(value) != {'baseUrl','expected','credentialFile'} or value['credentialFile'] != 'web-credential.json' or value['expected'].get('stationAirport') != airport:raise ValueError('Invalid Web connection template')
            from .security import validate_source
            from urllib.parse import urlparse
            if urlparse(validate_source(value['baseUrl'])).scheme != 'https':raise ValueError('Invalid Web source')
        result = {'airport':airport,'createdAt':manifest['createdAt'],**summary,'users':len(users),'webReconfigurationRequired':template.exists(),'recoveryPrepared':bool(target)}
        if target:
            with sqlite3.connect(root/'manager.sqlite', factory=ClosingConnection) as db:
                db.execute('PRAGMA trusted_schema=OFF')
                if 'upstream_sync' in schema(db):db.execute("UPDATE upstream_sync SET mode='manual'")
                if 'clock_state' in schema(db):db.execute('DELETE FROM clock_state')
            (root/'expected.sqlite').unlink()
            private(root/'recovery.json', encoded({**result,'requires':['Set LAN address and launch paths','Configure Web credential if needed','Configure OS time service','Isolate old manager before enabling LAN feed']}))
            # Rename only the validated recovery files, never active files.
            staged=root/'prepared';staged.mkdir(mode=0o700)
            for path in list(root.iterdir()):
                if path.is_file():path.rename(staged/path.name)
            if target.exists():raise ValueError('Recovery folder already exists')
            os.rename(staged,target)
        return result

class Backups:
    def __init__(self, store, security, upstream=None):
        self.store,self.security,self.upstream=store,security,upstream
        self.root=Path(store.path).resolve().parent/'backups'
        self.root.mkdir(mode=0o700, exist_ok=True)
        self.lock=threading.RLock()

    def create(self):
        with self.lock, self.security.lock, tempfile.TemporaryDirectory(dir=self.root) as temporary:
            root=Path(temporary); config=self.security.config();airport=config['airport']
            auth={k:config[k] for k in ('airport','username','salt','passwordHash','terminals')}
            auth['timezone']=config.get('timezone',sites.DEFAULT_ZONES.get(airport,'UTC'))
            users=self.security.users();validate_auth(auth,users,airport)
            snapshot=root/'manager.sqlite'
            with self.store.connect() as source, sqlite3.connect(snapshot, factory=ClosingConnection) as destination:source.backup(destination)
            summary=validate_database(snapshot,root,airport)
            payload={'manager.sqlite':snapshot.read_bytes(),'manager-auth.json':encoded(auth),'manager-auth.users.json':encoded(users),'site.json':encoded({'airport':airport,'timezone':summary['timezone']})}
            if self.upstream:
                source=json.loads(self.upstream.path.read_text(encoding='utf-8'))
                expected={key:source['expected'][key] for key in ('stationAirport','product','timezone','organizationId','airportId') if key in source['expected']}
                payload['web-connection.template.json']=encoded({'baseUrl':source['baseUrl'],'expected':expected,'credentialFile':'web-credential.json'})
            if sum(map(len,payload.values()))>MAX_BYTES:raise ValueError('Backup is too large')
            manifest={'format':FORMAT,'airport':airport,'createdAt':datetime.now(timezone.utc).isoformat(),'files':{name:{'bytes':len(body),'sha256':digest(body)} for name,body in payload.items()}}
            identifier=uuid.uuid4().hex;output=self.root/(identifier+'.zip')
            # Windows TemporaryDirectory has a restrictive creator-token ACL.
            # Create the archive in the destination directory so it inherits
            # the backup directory's ACL, including the ordinary logon user.
            pending=self.root/(identifier+'.pending')
            private(pending,b'')
            try:
                with zipfile.ZipFile(pending,'w',zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr('manifest.json',encoded(manifest))
                    for name,body in payload.items():archive.writestr(name,body)
                inspect_archive(pending,airport)
                os.replace(pending,output)
            finally:
                if pending.exists():pending.unlink()
            return {'id':identifier,**manifest,'summary':summary}

    def path(self, identifier):
        if not isinstance(identifier,str) or not re.fullmatch('[a-f0-9]{32}',identifier):raise ValueError('Invalid backup ID')
        path=self.root/(identifier+'.zip')
        if not path.is_file():raise ValueError('Backup not found')
        return path

    def status(self):
        entries=[]
        for path in sorted(self.root.glob('*.zip'),key=lambda p:p.stat().st_mtime,reverse=True):
            try:
                with zipfile.ZipFile(path) as z:manifest=json.loads(z.read('manifest.json'))
                if manifest.get('format')==FORMAT and manifest.get('airport')==self.security.config()['airport']:
                    entries.append({'id':path.stem,'createdAt':manifest['createdAt'],'bytes':path.stat().st_size})
            except (ValueError,KeyError,zipfile.BadZipFile):continue
        return {'backups':entries,'automatic':False,'maxBytes':MAX_BYTES}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Validate or prepare Pi-FIDS recovery in a new folder; never overwrite live data')
    parser.add_argument('archive');parser.add_argument('--airport',required=True);parser.add_argument('--output')
    args=parser.parse_args()
    try:print(json.dumps(inspect_archive(args.archive,args.airport,args.output),ensure_ascii=False,indent=2))
    except (ValueError,OSError,sqlite3.Error,zipfile.BadZipFile,KeyError,TypeError) as error:parser.exit(1,'Recovery rejected: '+str(error)+'\n')
