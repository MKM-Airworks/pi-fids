import json
import sqlite3
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
    return {key: data[key].strip() for key in ('airport', 'flightNumber', 'destination', 'time')} | {'languages': languages}


def effective_languages(flight, defaults):
    return flight.get('languages') or defaults


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS displays (airport TEXT NOT NULL, display_id TEXT NOT NULL, mode TEXT NOT NULL, airline TEXT NOT NULL, version INTEGER NOT NULL, PRIMARY KEY (airport, display_id))')
            db.execute('CREATE TABLE IF NOT EXISTS state (airport TEXT PRIMARY KEY, draft TEXT NOT NULL, published TEXT NOT NULL, version INTEGER NOT NULL)')
            for airport in ('SHI', 'ROR'):
                db.execute('INSERT OR IGNORE INTO state VALUES (?, ?, ?, 0)', (airport, '[]', '[]'))

    def connect(self):
        return sqlite3.connect(self.path)

    def read(self, airport):
        if airport not in ('SHI', 'ROR'):
            raise ValueError('Invalid airport')
        with self.connect() as db:
            row = db.execute('SELECT draft,published,version FROM state WHERE airport=?', (airport,)).fetchone()
        return {'airport': airport, 'draft': json.loads(row[0]), 'flights': json.loads(row[1]), 'version': row[2], 'preview': True}

    def add(self, data):
        flight = validate(data)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            raw = db.execute('SELECT draft FROM state WHERE airport=?', (flight['airport'],)).fetchone()[0]
            draft = json.loads(raw)
            if len(draft) >= 100:
                raise ValueError('Prototype limit: 100 flights')
            draft.append(flight)
            db.execute('UPDATE state SET draft=? WHERE airport=?', (json.dumps(draft, ensure_ascii=False), flight['airport']))

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
        return {'displayId': display_id, 'mode': row[0] if row else 'board', 'airline': row[1] if row else '', 'version': row[2] if row else 0}

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
        with self.connect() as db:
            db.execute('INSERT INTO displays VALUES (?,?,?,?,1) ON CONFLICT(airport,display_id) DO UPDATE SET mode=excluded.mode,airline=excluded.airline,version=displays.version+1', (airport, display_id, mode, airline))
