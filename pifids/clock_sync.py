"""Management OS clock reference and receiver display clock calibration."""
from datetime import datetime, timezone, timedelta
import time


def info(db):
    row=db.execute('SELECT offset,revision,last_sync,source FROM clock_state WHERE id=1').fetchone()
    offset,revision,last_sync,source=row or (0,0,None,'management-pc')
    return dict(utcNow=datetime.fromtimestamp(time.time()+offset,timezone.utc).isoformat(),offsetSeconds=offset,revision=revision,lastSync=last_sync,source=source,systemUtcNow=datetime.now(timezone.utc).isoformat())


def validate(data):
    if not isinstance(data,dict) or not isinstance(data.get('utcNow'),str):raise ValueError('Invalid management clock')
    try:
        stamp=datetime.fromisoformat(data['utcNow'])
        if stamp.tzinfo is None or stamp.utcoffset()!=timedelta(0):raise ValueError()
        value=stamp.timestamp()
    except (ValueError,OverflowError):raise ValueError('Invalid management clock')
    return value


def accept(db,data):
    stamp=validate(data)
    db.execute("INSERT INTO clock_state VALUES (1,?,1,?,'management-pc-lan') ON CONFLICT(id) DO UPDATE SET offset=excluded.offset,revision=clock_state.revision+1,last_sync=excluded.last_sync,source=excluded.source",(stamp-time.time(),datetime.now(timezone.utc).isoformat()))



def correct_os(store,data,service):
    if service is None:raise ValueError('Install the Windows OS clock service on the management PC first')
    store.read(data.get('airport'))
    if data.get('mode')!='set':raise ValueError('Invalid OS clock operation')
    revision=data.get('expectedRevision')
    if type(revision) is not int or revision<0:raise ValueError('Invalid clock revision')
    from .store import DraftConflict
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if info(db)['revision']!=revision:raise DraftConflict('Clock settings changed. Refresh before correcting.')
        service.set_local(data.get('targetLocal'))
        # Clock corrections now affect the OS; discard prototype application offsets.
        db.execute("INSERT INTO clock_state VALUES (1,0,1,?,'management-pc') ON CONFLICT(id) DO UPDATE SET offset=0,revision=clock_state.revision+1,last_sync=excluded.last_sync,source='management-pc'",(datetime.now(timezone.utc).isoformat(),))
