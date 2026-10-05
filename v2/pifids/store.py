import base64
import hashlib
import re
import json
import sqlite3
import uuid
from pathlib import Path

LANGUAGES = ('ja', 'en', 'zh-Hant', 'zh-Hans', 'ko')


def validate(data):
    if not isinstance(data, dict):
        raise ValueError('Invalid flight')
    if data.get('airport') not in ('SHI', 'ROR'):
        raise ValueError('Select SHI or ROR')
    for key in ('flightNumber', 'destination', 'time'):
        if not isinstance(data.get(key), str) or not data[key].strip() or len(data[key]) > 100:
            raise ValueError('Missing or invalid ' + key)
    import re
    if not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', data['time']):
        raise ValueError('Time must be HH:mm')
    languages = data.get('languages', [])
    if not isinstance(languages, list) or any(x not in LANGUAGES for x in languages) or len(set(languages)) != len(languages):
        raise ValueError('Invalid languages')
    logo = data.get('airlineLogo', '')
    if not isinstance(logo, str) or (logo and not re.fullmatch('[a-f0-9]{64}', logo)):
        raise ValueError('Invalid airline logo')
    direction = data.get('direction', 'departure')
    if direction not in ('departure', 'arrival'):
        raise ValueError('Invalid flight direction')
    extra = {}
    for key, limit in (('estimatedTime', 5), ('gate', 20), ('remark', 100)):
        value = data.get(key, '')
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError('Invalid ' + key)
        if key == 'estimatedTime' and value and not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', value):
            raise ValueError('Estimated time must be HH:mm')
        extra[key] = value.strip()
    return {key: data[key].strip() for key in ('airport', 'flightNumber', 'destination', 'time')} | {'languages': languages, 'airlineLogo': logo, 'direction': direction, **extra}


def effective_languages(flight, defaults):
    return flight.get('languages') or defaults


class DraftConflict(ValueError):
    pass


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS assets (airport TEXT NOT NULL, digest TEXT NOT NULL, name TEXT NOT NULL, mime TEXT NOT NULL, body BLOB NOT NULL, PRIMARY KEY (airport,digest))')
            db.execute('CREATE TABLE IF NOT EXISTS display_assets (airport TEXT NOT NULL, display_id TEXT NOT NULL, logo TEXT NOT NULL, image TEXT NOT NULL, PRIMARY KEY (airport,display_id))')
            db.execute('CREATE TABLE IF NOT EXISTS displays (airport TEXT NOT NULL, display_id TEXT NOT NULL, mode TEXT NOT NULL, airline TEXT NOT NULL, version INTEGER NOT NULL, PRIMARY KEY (airport, display_id))')
            db.execute('CREATE TABLE IF NOT EXISTS state (airport TEXT PRIMARY KEY, draft TEXT NOT NULL, published TEXT NOT NULL, version INTEGER NOT NULL)')
            if 'draft_revision' not in [row[1] for row in db.execute('PRAGMA table_info(state)')]:
                db.execute('ALTER TABLE state ADD COLUMN draft_revision INTEGER NOT NULL DEFAULT 0')
            for airport in ('SHI', 'ROR'):
                db.execute('INSERT OR IGNORE INTO state (airport,draft,published,version) VALUES (?, ?, ?, 0)', (airport, '[]', '[]'))
                draft = json.loads(db.execute('SELECT draft FROM state WHERE airport=?', (airport,)).fetchone()[0])
                if any('id' not in flight for flight in draft):
                    for flight in draft:
                        flight.setdefault('id', uuid.uuid4().hex)
                    db.execute('UPDATE state SET draft=?,draft_revision=draft_revision+1 WHERE airport=?', (json.dumps(draft, ensure_ascii=False), airport))

    def connect(self):
        return sqlite3.connect(self.path)

    def read(self, airport):
        if airport not in ('SHI', 'ROR'):
            raise ValueError('Invalid airport')
        with self.connect() as db:
            row = db.execute('SELECT draft,published,version,draft_revision FROM state WHERE airport=?', (airport,)).fetchone()
        return {'airport': airport, 'draft': json.loads(row[0]), 'flights': json.loads(row[1]), 'version': row[2], 'preview': True, 'draftRevision': row[3]}

    def add(self, data):
        flight = validate(data)
        if flight['airlineLogo']:
            self.asset(flight['airport'], flight['airlineLogo'])
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            raw = db.execute('SELECT draft FROM state WHERE airport=?', (flight['airport'],)).fetchone()[0]
            draft = json.loads(raw)
            if len(draft) >= 100:
                raise ValueError('Prototype limit: 100 flights')
            flight['id'] = uuid.uuid4().hex
            draft.append(flight)
            db.execute('UPDATE state SET draft=?,draft_revision=draft_revision+1 WHERE airport=?', (json.dumps(draft, ensure_ascii=False), flight['airport']))

    def change_flight(self, data, delete=False):
        airport = data.get('airport')
        self.read(airport)
        flight_id = data.get('id')
        revision = data.get('expectedDraftRevision')
        if not isinstance(flight_id, str) or not re.fullmatch('[a-f0-9]{32}', flight_id):
            raise ValueError('Invalid flight ID')
        if type(revision) is not int or revision < 0:
            raise ValueError('Invalid draft revision')
        replacement = None if delete else validate(data)
        if replacement and replacement['airlineLogo']:
            self.asset(airport, replacement['airlineLogo'])
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            raw, current = db.execute('SELECT draft,draft_revision FROM state WHERE airport=?', (airport,)).fetchone()
            if current != revision:
                raise DraftConflict('Draft changed. Refresh and select the flight again.')
            draft = json.loads(raw)
            index = next((i for i, flight in enumerate(draft) if flight.get('id') == flight_id), None)
            if index is None:
                raise ValueError('Flight not found for airport')
            if delete:
                draft.pop(index)
            else:
                draft[index] = {**replacement, 'id': flight_id}
            db.execute('UPDATE state SET draft=?,draft_revision=draft_revision+1 WHERE airport=?', (json.dumps(draft, ensure_ascii=False), airport))

    def publish(self, airport):
        if airport not in ('SHI', 'ROR'):
            raise ValueError('Invalid airport')
        with self.connect() as db:
            db.execute('UPDATE state SET published=draft,version=version+1 WHERE airport=?', (airport,))

    def display(self, airport, display_id):
        self.read(airport)
        self.validate_display_id(display_id)
        with self.connect() as db:
            row = db.execute('SELECT mode,airline,version FROM displays WHERE airport=? AND display_id=?', (airport, display_id)).fetchone()
        with self.connect() as db:
            refs = db.execute('SELECT logo,image FROM display_assets WHERE airport=? AND display_id=?', (airport,display_id)).fetchone()
        return {'logo': refs[0] if refs else '', 'image': refs[1] if refs else '', 'displayId': display_id, 'mode': row[0] if row else 'board', 'airline': row[1] if row else '', 'version': row[2] if row else 0}

    @staticmethod
    def validate_display_id(display_id):
        import re
        if not isinstance(display_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', display_id):
            raise ValueError('Invalid display ID')

    def set_display(self, data):
        airport, display_id = data.get('airport'), data.get('displayId')
        self.read(airport)
        self.validate_display_id(display_id)
        mode, airline = data.get('mode'), data.get('airline', '')
        if mode not in ('board', 'counter', 'gate'):
            raise ValueError('Invalid display mode')
        if not isinstance(airline, str) or len(airline) > 100 or (mode != 'board' and not airline.strip()):
            raise ValueError('Enter airline name')
        airline = airline.strip() if mode != 'board' else ''
        refs = [data.get(key, '') for key in ('logo', 'image')]
        for digest in refs:
            if not isinstance(digest, str):
                raise ValueError('Invalid image ID')
            if digest:
                self.asset(airport, digest)
        with self.connect() as db:
            db.execute('INSERT INTO display_assets VALUES (?,?,?,?) ON CONFLICT(airport,display_id) DO UPDATE SET logo=excluded.logo,image=excluded.image', (airport,display_id,*refs))
            db.execute('INSERT INTO displays VALUES (?,?,?,?,1) ON CONFLICT(airport,display_id) DO UPDATE SET mode=excluded.mode,airline=excluded.airline,version=displays.version+1', (airport, display_id, mode, airline))

    def upload_asset(self, data):
        airport = data.get('airport')
        self.read(airport)
        name = data.get('name')
        if not isinstance(name, str) or not 1 <= len(name) <= 100:
            raise ValueError('Invalid image name')
        try:
            body = base64.b64decode(data.get('body', ''), validate=True)
        except (ValueError, TypeError):
            raise ValueError('Invalid image data')
        if not 0 < len(body) <= 2 * 1024 * 1024:
            raise ValueError('Image limit: 2 MiB')
        if body.startswith(b'\x89PNG\r\n\x1a\n') and len(body) >= 24 and body[12:16] == b'IHDR':
            width = int.from_bytes(body[16:20], 'big')
            height = int.from_bytes(body[20:24], 'big')
            if not 0 < width <= 4096 or not 0 < height <= 4096:
                raise ValueError('PNG dimensions must be 1..4096')
            mime = 'image/png'
        elif body.startswith(b'\xff\xd8\xff') and body.endswith(b'\xff\xd9'):
            mime = 'image/jpeg'
        else:
            raise ValueError('PNG or JPEG required')
        digest = hashlib.sha256(body).hexdigest()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            count = db.execute('SELECT count(*) FROM assets WHERE airport=?', (airport,)).fetchone()[0]
            exists = db.execute('SELECT 1 FROM assets WHERE airport=? AND digest=?', (airport,digest)).fetchone()
            if count >= 30 and not exists:
                raise ValueError('Prototype limit: 30 images per airport')
            db.execute('INSERT OR IGNORE INTO assets VALUES (?,?,?,?,?)', (airport,digest,name,mime,body))
        return digest

    def assets(self, airport):
        self.read(airport)
        with self.connect() as db:
            return [{'digest': r[0], 'name': r[1]} for r in db.execute('SELECT digest,name FROM assets WHERE airport=? ORDER BY name,digest', (airport,))]

    def asset(self, airport, digest):
        self.read(airport)
        if not isinstance(digest, str) or not re.fullmatch('[a-f0-9]{64}', digest):
            raise ValueError('Invalid image ID')
        with self.connect() as db:
            row = db.execute('SELECT mime,body FROM assets WHERE airport=? AND digest=?', (airport,digest)).fetchone()
        if not row:
            raise ValueError('Image not found for airport')
        return row
