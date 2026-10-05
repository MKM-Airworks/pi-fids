"""Named terminals and reusable signage choices, owned by the local manager."""
import sqlite3
from .store import retention


def init(store):
    with store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS terminals (airport TEXT NOT NULL,display_id TEXT NOT NULL,name TEXT NOT NULL,PRIMARY KEY(airport,display_id),UNIQUE(airport,name))')
        db.execute('CREATE TABLE IF NOT EXISTS terminal_layouts (airport TEXT NOT NULL,display_id TEXT NOT NULL,name TEXT NOT NULL,version INTEGER NOT NULL,PRIMARY KEY(airport,display_id))')
        db.execute('CREATE TABLE IF NOT EXISTS signage_profiles (airport TEXT NOT NULL,name TEXT NOT NULL,mode TEXT NOT NULL,airline TEXT NOT NULL,logo TEXT NOT NULL,image TEXT NOT NULL,PRIMARY KEY(airport,name))')
        db.execute('INSERT OR IGNORE INTO terminals SELECT airport,display_id,display_id FROM displays')


def label(value):
    if not isinstance(value,str) or not value.strip() or len(value)>100:
        raise ValueError('Enter a name (up to 100 characters)')
    return value.strip()


def listing(store,airport):
    store.read(airport);init(store)
    with store.connect() as db:
        terminals=[dict(displayId=row[0],name=row[1],profileName=row[2]) for row in db.execute('SELECT t.display_id,t.name,l.name FROM terminals t LEFT JOIN terminal_layouts l ON l.airport=t.airport AND l.display_id=t.display_id WHERE t.airport=? ORDER BY t.name',(airport,))]
        profiles=[dict(zip(('name','mode','airline','logo','image'),row)) for row in db.execute('SELECT name,mode,airline,logo,image FROM signage_profiles WHERE airport=? ORDER BY name',(airport,))]
    return dict(terminals=terminals,profiles=profiles)


def save_terminal(store,data):
    airport,display_id=data.get('airport'),data.get('displayId')
    store.read(airport);store.validate_display_id(display_id);name=label(data.get('name'));timing=retention(data);init(store)
    try:
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO terminals VALUES (?,?,?) ON CONFLICT(airport,display_id) DO UPDATE SET name=excluded.name',(airport,display_id,name))
            db.execute('INSERT INTO displays VALUES (?,?,\'board\',\'\',1) ON CONFLICT(airport,display_id) DO UPDATE SET version=displays.version+1',(airport,display_id))
            db.execute('INSERT INTO display_timing VALUES (?,?,?,?) ON CONFLICT(airport,display_id) DO UPDATE SET departure=excluded.departure,arrival=excluded.arrival',(airport,display_id,timing['departureHideMinutes'],timing['arrivalHideMinutes']))
    except sqlite3.IntegrityError:
        raise ValueError('Another terminal already uses this name')


def save_profile(store,data):
    airport=data.get('airport');store.read(airport);name=label(data.get('name'))
    mode=data.get('mode');airline=label(data.get('airline'))
    if mode not in ('counter','gate'):
        raise ValueError('Select check-in counter or boarding gate')
    refs=[data.get(key,'') for key in ('logo','image')]
    for digest in refs:
        if not isinstance(digest,str):raise ValueError('Invalid image ID')
        if digest:store.asset(airport,digest)
    init(store)
    with store.connect() as db:
        db.execute('INSERT INTO signage_profiles VALUES (?,?,?,?,?,?) ON CONFLICT(airport,name) DO UPDATE SET mode=excluded.mode,airline=excluded.airline,logo=excluded.logo,image=excluded.image',(airport,name,mode,airline,*refs))


def apply(store,data):
    airport,display_id=data.get('airport'),data.get('displayId');store.read(airport);store.validate_display_id(display_id);init(store)
    profile_name=data.get('profileName')
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if not db.execute('SELECT 1 FROM terminals WHERE airport=? AND display_id=?',(airport,display_id)).fetchone():
            raise ValueError('Register the terminal first')
        if profile_name=='':
            mode,airline,logo,image='board','','',''
        else:
            name=label(profile_name)
            row=db.execute('SELECT mode,airline,logo,image FROM signage_profiles WHERE airport=? AND name=?',(airport,name)).fetchone()
            if not row:raise ValueError('Display layout not found for airport')
            mode,airline,logo,image=row
        db.execute('INSERT INTO displays VALUES (?,?,?,?,1) ON CONFLICT(airport,display_id) DO UPDATE SET mode=excluded.mode,airline=excluded.airline,version=displays.version+1',(airport,display_id,mode,airline))
        db.execute('INSERT INTO display_assets VALUES (?,?,?,?) ON CONFLICT(airport,display_id) DO UPDATE SET logo=excluded.logo,image=excluded.image',(airport,display_id,logo,image))
        version=db.execute('SELECT version FROM displays WHERE airport=? AND display_id=?',(airport,display_id)).fetchone()[0]
        db.execute('INSERT INTO terminal_layouts VALUES (?,?,?,?) ON CONFLICT(airport,display_id) DO UPDATE SET name=excluded.name,version=excluded.version',(airport,display_id,profile_name,version))
