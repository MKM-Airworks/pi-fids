"""Publish each local service day from the last verified seasonal release.

No network or Web credentials are needed. Published operations from earlier
days remain separate from today's instance while any screen still needs them.
"""
import json
import threading
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from .store import DraftConflict


def init_tables(store):
    from .seasonal_csv import init_tables as init_csv
    init_csv(store)
    with store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS daily_rollover (airport TEXT PRIMARY KEY,service_date TEXT,result TEXT NOT NULL,checked_at TEXT NOT NULL)')


def status(store, airport):
    with store.connect() as db:
        exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='daily_rollover'").fetchone()
        row = db.execute('SELECT service_date,result,checked_at FROM daily_rollover WHERE airport=?',(airport,)).fetchone() if exists else None
    return {'dailySchedule':{'enabled':True,'pollSeconds':60,'serviceDate':row[0] if row else None,'result':row[1] if row else 'waiting','lastCheck':row[2] if row else None}}


def operation_key(flight):
    return (flight.get('direction','departure'),flight['flightNumber'],flight['serviceDate'])


def carryovers(db, airport, flights, service_date, zone, now=None):
    """Match the board's actual > estimated > scheduled expiry, conservatively
    keeping a row until the longest configured screen retention has elapsed.
    """
    now = now or datetime.combine(datetime.fromisoformat(service_date).date(),datetime.min.time(),ZoneInfo(zone))
    limits = db.execute('SELECT departure,arrival FROM display_timing WHERE airport=?',(airport,)).fetchall()
    departure = max([10]+[row[0] for row in limits])
    arrival = max([120]+[row[1] for row in limits])
    kept = []
    for flight in flights:
        if flight['serviceDate'] >= service_date:
            continue
        key = 'actual' if flight.get('actualTime') else 'estimated' if flight.get('estimatedTime') else None
        day = (flight.get(key+'Date') or flight['serviceDate']) if key else flight['serviceDate']
        time = flight[key+'Time'] if key else flight['time']
        base = datetime.fromisoformat(day+'T'+time).replace(tzinfo=ZoneInfo(zone))
        minutes = arrival if flight.get('direction','departure')=='arrival' else departure
        # Epoch arithmetic also matches the browser across daylight-saving changes.
        if now.timestamp() < base.timestamp()+minutes*60:
            kept.append(flight)
    return kept


class DailySchedules:
    def __init__(self, store):
        self.store = store
        init_tables(store)

    def step(self, now=None):
        from .upstream import init_tables, verify, project, SCOPE
        init_tables(self.store)
        with self.store.connect() as db:
            airports = [row[0] for row in db.execute('SELECT airport FROM upstream_cache UNION SELECT airport FROM local_schedule_cache')]
        if getattr(self.store,'installed_airport',None):airports=[a for a in airports if a==self.store.installed_airport]
        for airport in airports:
            zone = self.store.timezone(airport)
            local = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo(zone))
            day = local.date().isoformat()
            result = 'failed'
            try:
                with self.store.as_actor({'username':'Saved seasonal schedule / daily rollover','role':'system'}):
                    with self.store.connect() as db:
                        db.execute('BEGIN IMMEDIATE')
                        csv_cache=db.execute('SELECT body,flight_ids,service_date,baseline FROM local_schedule_cache WHERE airport=?',(airport,)).fetchone()
                        cache = db.execute('SELECT manifest,body FROM upstream_cache WHERE airport=?',(airport,)).fetchone()
                        previous = db.execute('SELECT flight_ids,service_date,baseline FROM upstream_imports WHERE airport=?',(airport,)).fetchone()
                        if csv_cache:previous=csv_cache[1:]
                        windows={'departure':0,'arrival':0}
                        for setting in db.execute('SELECT body FROM board_settings WHERE airport=?',(airport,)):
                            config=json.loads(setting[0])
                            for direction in windows:
                                value=config.get(direction+'ShowMinutes')
                                if type(value) is int:windows[direction]=max(windows[direction],value)
                        lookahead=max(windows.values())
                        if not previous:
                            result = 'waiting_for_first_import'
                        elif previous[1] >= day and not lookahead:
                            result = 'current' if previous[1] == day else 'future_publication'
                        else:
                            if csv_cache:
                                body=json.loads(csv_cache[0]);manifest={'dataVersion':0}
                            else:
                                manifest = json.loads(cache[0])
                                expected = {key:manifest[key] for key in SCOPE}
                                if expected['stationAirport'] != airport or expected['timezone'] != zone:
                                    raise ValueError('Cached seasonal schedule scope differs from installation')
                                # Preview permission was checked when accepting this cache;
                                # this does not fetch or accept any new release.
                                body = verify(manifest,cache[1],{**expected,'allowPreview':True})
                            if not body['coverage']['from'] <= day <= body['coverage']['to']:
                                result = 'expired' if day > body['coverage']['to'] else 'not_yet_effective'
                            else:
                                draft,published = db.execute('SELECT draft,published FROM state WHERE airport=?',(airport,)).fetchone()
                                if json.loads(draft) != json.loads(published):
                                    raise DraftConflict('Unpublished changes require review before daily publication')
                                old = json.loads(published)
                                ids = set(json.loads(previous[0]))
                                imported = [row for row in old if row['id'] in ids]
                                manual = [row for row in old if row['id'] not in ids]
                                today = project(body,day)
                                for offset in range(1,(lookahead+1439)//1440+1):
                                    future=(local.date()+timedelta(days=offset)).isoformat()
                                    if future>body['coverage']['to']:break
                                    for row in project(body,future):
                                        start=datetime.fromisoformat(future+'T'+row['time']).replace(tzinfo=ZoneInfo(zone))
                                        if local.timestamp()>=start.timestamp()-windows[row['direction']]*60:today.append(row)
                                fresh_baseline=json.loads(json.dumps(today))
                                old_by_operation={operation_key(row):row for row in imported}
                                old_by_flight = {(row.get('direction','departure'),row['flightNumber']):row for row in imported}
                                for row in today:
                                    settings = old_by_flight.get((row['direction'],row['flightNumber']),{})
                                    for key in ('airlineLogo','languages'):
                                        if key in settings:row[key] = settings[key]
                                    existing=old_by_operation.get(operation_key(row))
                                    if existing:row.update(existing)
                                kept = carryovers(db,airport,imported,day,zone,local)
                                if {operation_key(row) for row in manual} & {operation_key(row) for row in today}:
                                    raise DraftConflict('A manual flight conflicts with today\'s schedule')
                                combined = manual+kept+today
                                if len(combined)>100:raise ValueError('Current FIDS limit: 100 flights including carried flights')
                                if combined==old and previous[1]==day:
                                    db.execute('INSERT INTO daily_rollover VALUES (?,?,?,?) ON CONFLICT(airport) DO UPDATE SET service_date=excluded.service_date,result=excluded.result,checked_at=excluded.checked_at',(airport,day,'current',local.isoformat()))
                                    continue
                                encoded = json.dumps(combined)
                                db.execute('UPDATE state SET draft=?,published=?,version=version+1,draft_revision=draft_revision+1 WHERE airport=?',(encoded,encoded,airport))
                                if csv_cache:
                                    db.execute('UPDATE local_schedule_cache SET flight_ids=?,service_date=?,baseline=? WHERE airport=?',(json.dumps([row['id'] for row in kept+today]),day,json.dumps(fresh_baseline),airport))
                                else:
                                    db.execute('UPDATE upstream_imports SET flight_ids=?,service_date=?,web_version=?,baseline=? WHERE airport=?',(json.dumps([row['id'] for row in kept+today]),day,manifest['dataVersion'],json.dumps(fresh_baseline),airport))
                                if not csv_cache:db.execute('INSERT INTO upstream_sync (airport,last_publish,published_date,published_version) VALUES (?,?,?,?) ON CONFLICT(airport) DO UPDATE SET last_publish=excluded.last_publish,published_date=excluded.published_date,published_version=excluded.published_version',(airport,local.isoformat(),day,manifest['dataVersion']))
                                self.store.audit(db,airport,'schedule.daily-publish',day,old,combined,source='CSV seasonal schedule' if csv_cache else 'Saved seasonal schedule')
                                result = 'published'
            except DraftConflict:
                result = 'review_required'
            except (ValueError,TypeError,KeyError,OSError):
                result = 'failed'
            with self.store.connect() as db:
                db.execute('INSERT INTO daily_rollover VALUES (?,?,?,?) ON CONFLICT(airport) DO UPDATE SET service_date=excluded.service_date,result=excluded.result,checked_at=excluded.checked_at',(airport,day,result,local.isoformat()))

    def start(self):
        stop = threading.Event()
        def run():
            while not stop.is_set():
                try:self.step()
                except Exception:pass  # Keep the last publication and retry next minute.
                stop.wait(60)
        threading.Thread(target=run,name='Saved seasonal schedule rollover',daemon=True).start()
        return stop
