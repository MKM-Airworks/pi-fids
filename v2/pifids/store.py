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
