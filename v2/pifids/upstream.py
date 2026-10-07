"""Read the unchanged MKM inspection-record API; stage departures for review."""
import hashlib
import json
import re
import threading
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler
from urllib.parse import urlparse

from .receiver import NoRedirect
from .security import validate_source
from .store import DraftConflict, validate

SCOPE = ('organizationId', 'airportId', 'product', 'stationAirport', 'timezone')
IDENTITY = ('schemaVersion', *SCOPE, 'releaseId', 'dataVersion', 'publishedAt', 'preview', 'coverage')
ZONES = {'SHI':'Asia/Tokyo', 'ROR':'Pacific/Palau'}
SCHEMAS = Path(__file__).parent/'contracts'
PROFILES = {'inspection-record':('','/v1/receiver'), 'pi-fids':('fids-','/v1/fids-receiver')}

def contract(expected, kind):
    prefix, _ = PROFILES[expected['product']]
    return json.loads((SCHEMAS/(prefix+kind+'-v1.schema.json')).read_text())


def schema_check(value, schema):
    kind = schema.get('type')
    valid = {'object':isinstance(value,dict), 'array':isinstance(value,list), 'string':isinstance(value,str), 'integer':type(value) is int, 'boolean':type(value) is bool}
    if kind and not valid[kind]:
        raise ValueError('Invalid distribution field type')
    if 'const' in schema and value != schema['const'] or 'enum' in schema and value not in schema['enum']:
        raise ValueError('Unsupported distribution value')
    if kind == 'object':
        if any(key not in value for key in schema.get('required', [])) or schema.get('additionalProperties') is False and any(key not in schema['properties'] for key in value):
            raise ValueError('Invalid distribution fields')
        for key, item in value.items():
            if key in schema.get('properties', {}):
                schema_check(item, schema['properties'][key])
    elif kind == 'array':
        if not schema.get('minItems',0) <= len(value) <= schema.get('maxItems',100000):
            raise ValueError('Invalid distribution list length')
        if schema.get('uniqueItems') and len({json.dumps(item,sort_keys=True) for item in value}) != len(value):
            raise ValueError('Duplicate distribution list values')
        for item in value:
            schema_check(item,schema['items'])
    elif kind == 'integer':
        if not schema.get('minimum',-2**53) <= value <= schema.get('maximum',2**53-1):
            raise ValueError('Invalid distribution number')
    elif kind == 'string':
        if not schema.get('minLength',0) <= len(value) <= schema.get('maxLength',10000) or 'pattern' in schema and not re.fullmatch(schema['pattern'],value):
            raise ValueError('Invalid distribution string')
        fmt = schema.get('format')
        if fmt == 'uuid' and str(uuid.UUID(value)) != value:
            raise ValueError('Invalid distribution UUID')
        if fmt == 'date' and date.fromisoformat(value).isoformat() != value:
            raise ValueError('Invalid distribution date')
        if fmt == 'date-time':
            timestamp = datetime.fromisoformat(value.replace('Z','+00:00'))
            if 'T' not in value or timestamp.utcoffset() != timedelta(0):
                raise ValueError('Publication timestamp must be UTC')


def parse_json(raw):
    def object_pairs(pairs):
        data = {}
        for key, value in pairs:
            if key in data:
                raise ValueError('Duplicate JSON fields')
            data[key] = value
        return data
    def invalid_constant(value):
        raise ValueError('Invalid JSON number')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=object_pairs, parse_constant=invalid_constant)


def local_date():
    # SHI and ROR both use UTC+09:00, without seasonal clock changes.
    return datetime.now(timezone(timedelta(hours=9))).date()


def verify(manifest, raw, expected, previous=None):
    schema_check(manifest,contract(expected,'manifest'))
    if any(manifest[key] != expected[key] for key in SCOPE):
        raise ValueError('Distribution scope mismatch')
    if manifest['preview'] and expected.get('allowPreview') is not True:
        raise ValueError('Preview data is disabled')
    if manifest['dataPath'] != PROFILES[expected['product']][1]+'/releases/'+manifest['releaseId']:
        raise ValueError('Invalid release path')
    if previous:
        if any(previous[key] != manifest[key] for key in SCOPE):
            raise ValueError('Changing distribution scope requires a separate cache')
        if manifest['dataVersion'] < previous['dataVersion']:
            raise ValueError('Older Web version rejected')
        if manifest['dataVersion'] == previous['dataVersion'] and any(manifest[key] != previous[key] for key in (*IDENTITY,'sha256','byteLength')):
            raise ValueError('Published Web version changed')
    if len(raw) != manifest['byteLength'] or len(raw) > 4*1024*1024 or hashlib.sha256(raw).hexdigest() != manifest['sha256']:
        raise ValueError('Release integrity failure')
    body = parse_json(raw)
    schema_check(body,contract(expected,'release'))
    if any(body[key] != manifest[key] for key in IDENTITY):
        raise ValueError('Manifest/release mismatch')
    coverage = body['coverage']
    if coverage['from'] > coverage['to']:
        raise ValueError('Invalid coverage')
    flights = body['flights']
    if (body['declaration'] == 'no_flights') != (len(flights) == 0):
        raise ValueError('Invalid no-flight declaration')
    identifiers = set()
    groups = {}
    for flight in flights:
        direction = flight.get('direction','departure')
        if body['product']=='pi-fids':
            time_statuses = ('','FE','NI','OT','DL','DP','NO') if direction=='departure' else ('','FE','OT','DL','LD','NO')
            if flight['timeStatus'] not in time_statuses or direction=='arrival' and flight['boardingStatus']:
                raise ValueError('Invalid direction-specific FIDS status')
        endpoint = flight['origin'] if direction=='departure' else flight['destination']
        if endpoint != body['stationAirport'] or not coverage['from'] <= flight['validFrom'] <= flight['validTo'] <= coverage['to']:
            raise ValueError('Invalid flight airport or validity')
        if flight['id'] in identifiers or not flight['flightNumber'].startswith(flight['airlineCode']):
            raise ValueError('Invalid schedule identity')
        identifiers.add(flight['id'])
        groups.setdefault((direction,flight['flightNumber']),[]).append(flight)
    for schedules in groups.values():
        ordered = sorted(schedules,key=lambda flight:flight['validFrom'])
        for index, first in enumerate(ordered):
            for second in ordered[index+1:]:
                if second['validFrom'] > first['validTo']:
                    break
                start = date.fromisoformat(max(first['validFrom'],second['validFrom']))
                end = date.fromisoformat(min(first['validTo'],second['validTo']))
                days = set(first['operatingDays']) & set(second['operatingDays'])
                if any((start+timedelta(days=offset)).isoweekday() in days for offset in range(min(7,(end-start).days+1))):
                    raise ValueError('Overlapping operating flight schedules')
    active = sum(flight['validFrom'] <= manifest['localDate'] <= flight['validTo'] for flight in flights)
    status = 'not_yet_effective' if manifest['localDate'] < coverage['from'] else 'expired' if manifest['localDate'] > coverage['to'] else 'no_flights' if body['declaration'] == 'no_flights' else 'available' if active else 'no_active_schedules'
    if manifest['activeScheduleCount'] != active or manifest['status'] != status:
        raise ValueError('Invalid manifest applicability')
    return body


def remark(flight):
    if flight['status']=='CD':
        return 'Cancelled'
    if flight.get('status')=='DL' or flight.get('timeStatus')=='DL':
        return 'Delayed'
    boarding = {'boarding':'Boarding','final_call':'Final call','gate_closed':'Gate closed'}.get(flight.get('boardingStatus'))
    return boarding or {'DP':'Departed','LD':'Arrived'}.get(flight.get('timeStatus'), {'DP':'Departed','LD':'Arrived'}.get(flight['status'],''))

def project(body, service_date):
    day = date.fromisoformat(service_date)
    if day.isoformat() != service_date or not body['coverage']['from'] <= service_date <= body['coverage']['to']:
        raise ValueError('Service date is outside Web coverage')
    rows = []
    for flight in body['flights']:
        if flight['validFrom'] <= service_date <= flight['validTo'] and day.isoweekday() in flight['operatingDays']:
            stable = json.dumps([*(body[key] for key in SCOPE), flight['id']],separators=(',',':'))
            row = validate({'serviceDate':service_date,'airport':body['stationAirport'],'flightNumber':flight['flightNumber'],'destination':flight['destination'] if flight.get('direction','departure')=='departure' else flight['origin'],'time':flight.get('scheduledTime',flight.get('scheduledDeparture')), 'direction':flight.get('direction','departure'),'estimatedTime':flight.get('estimatedTime',''),'gate':flight.get('gate',''), 'remark':remark(flight)})
            rows.append({**row, 'id':hashlib.sha256(stable.encode()).hexdigest()[:32]})
    if len(rows) > 100:
        raise ValueError('Current FIDS limit: 100 daily flights')
    return sorted(rows,key=lambda flight:(flight['time'],flight['flightNumber']))


class Upstream:
    def __init__(self, store, config_path):
        self.store = store
        self.path = Path(config_path)
        self.lock = threading.Lock()
        self.connection()
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS upstream_cache (airport TEXT PRIMARY KEY,manifest TEXT NOT NULL,body BLOB NOT NULL,checked_at TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS upstream_imports (airport TEXT PRIMARY KEY,flight_ids TEXT NOT NULL,service_date TEXT NOT NULL,web_version INTEGER NOT NULL,baseline TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS upstream_attempts (airport TEXT PRIMARY KEY,attempted_at TEXT NOT NULL,result TEXT NOT NULL)')

    def connection(self):
        config = json.loads(self.path.read_text(encoding='utf-8'))
        source = validate_source(config['baseUrl'])
        parsed = urlparse(source)
        if parsed.scheme != 'https' and not (config.get('allowLoopback') is True and parsed.hostname == '127.0.0.1' and parsed.scheme == 'http'):
            raise ValueError('Web source requires HTTPS; only explicit localhost tests allow HTTP')
        expected = config['expected']
        if expected.get('stationAirport') not in ZONES or expected.get('timezone') != ZONES[expected['stationAirport']] or expected.get('product') not in PROFILES:
            raise ValueError('Unsupported Web scope or airport timezone')
        for key in ('organizationId','airportId'):
            if str(uuid.UUID(expected[key])) != expected[key]:
                raise ValueError('Invalid expected scope')
        credential_path = Path(config['credentialFile'])
        if not credential_path.is_absolute():
            credential_path = self.path.parent/credential_path
        token = json.loads(credential_path.read_text(encoding='utf-8'))['token']
        if not isinstance(token,str) or not 32 <= len(token) <= 1024 or not token.isascii() or any(char.isspace() for char in token):
            raise ValueError('Invalid Web credential')
        return source, expected, token

    def cached(self, airport):
        with self.store.connect() as db:
            return db.execute('SELECT manifest,body,checked_at FROM upstream_cache WHERE airport=?',(airport,)).fetchone()

    def require_airport(self, airport):
        _, expected, _ = self.connection()
        if airport != expected['stationAirport']:
            raise ValueError('Web connection is configured for another airport')
        return expected

    def fetch(self, airport):
        with self.lock:
            source, expected, token = self.connection()
            if airport != expected['stationAirport']:
                raise ValueError('Web connection is configured for another airport')
            attempted = datetime.now(timezone.utc).isoformat()
            result = 'failed'
            try:
                opener = build_opener(ProxyHandler({}),NoRedirect())
                def get(path, limit):
                    request = Request(source+path,headers={'Authorization':'Bearer '+token,'Accept':'application/json','User-Agent':'MKM-PiFIDS/2.0'})
                    with opener.open(request,timeout=10) as response:
                        if response.status != 200 or response.headers.get_content_type() != 'application/json':
                            raise ValueError('Invalid Web response')
                        raw = response.read(limit+1)
                    if len(raw) > limit:
                        raise ValueError('Web response exceeds limit')
                    return raw
                manifest = parse_json(get(PROFILES[expected['product']][1]+'/manifest',65536))
                schema_check(manifest,contract(expected,'manifest'))
                if any(manifest[key] != expected[key] for key in SCOPE) or manifest['dataPath'] != PROFILES[expected['product']][1]+'/releases/'+manifest['releaseId']:
                    raise ValueError('Unexpected Web scope or release path')
                old = self.cached(airport)
                raw = get(manifest['dataPath'],4*1024*1024)
                verify(manifest,raw,expected,parse_json(old[0].encode()) if old else None)
                with self.store.connect() as db:
                    db.execute('INSERT INTO upstream_cache VALUES (?,?,?,?) ON CONFLICT(airport) DO UPDATE SET manifest=excluded.manifest,body=excluded.body,checked_at=excluded.checked_at',(airport,json.dumps(manifest),raw,attempted))
                result = 'verified'
            except HTTPError as error:
                result = 'unauthorized' if error.code in (401,403) else 'not_published' if error.code == 404 else 'unavailable'
                raise ValueError('Web '+result+'. Previous data retained.') from None
            except (URLError,TimeoutError,OSError):
                result = 'unavailable'
                raise ValueError('Web unavailable. Previous data retained.') from None
            finally:
                with self.store.connect() as db:
                    db.execute('INSERT INTO upstream_attempts VALUES (?,?,?) ON CONFLICT(airport) DO UPDATE SET attempted_at=excluded.attempted_at,result=excluded.result',(airport,attempted,result))
        return self.info(airport)

    def info(self, airport, service_date=None):
        expected = self.require_airport(airport)
        service_date = service_date or local_date().isoformat()
        if date.fromisoformat(service_date).isoformat() != service_date:
            raise ValueError('Invalid service date')
        cache = self.cached(airport)
        with self.store.connect() as db:
            attempt = db.execute('SELECT attempted_at,result FROM upstream_attempts WHERE airport=?',(airport,)).fetchone()
            imported = db.execute('SELECT service_date,web_version FROM upstream_imports WHERE airport=?',(airport,)).fetchone()
        result = {'configured':True,'serviceDate':service_date,'lastAttempt':attempt[0] if attempt else None,'lastResult':attempt[1] if attempt else None,'lastImportDate':imported[0] if imported else None,'lastImportVersion':imported[1] if imported else None,'flights':[],'canImport':False}
        if not cache:
            return result
        manifest = parse_json(cache[0].encode())
        if any(manifest[key] != expected[key] for key in SCOPE):
            raise ValueError('Cached Web scope differs from connection settings')
        body = verify(manifest,cache[1],expected)
        result.update({'webVersion':manifest['dataVersion'],'preview':manifest['preview'],'coverage':manifest['coverage'],'lastSuccess':cache[2],'declaration':body['declaration']})
        if not body['coverage']['from'] <= service_date <= body['coverage']['to']:
            result['status'] = 'not_yet_effective' if service_date < body['coverage']['from'] else 'expired'
            return result
        rows = project(body,service_date)
        active = any(flight['validFrom'] <= service_date <= flight['validTo'] for flight in body['flights'])
        result.update({'flights':rows,'status':'no_flights' if body['declaration']=='no_flights' else 'available' if rows else 'no_operating_flights' if active else 'no_active_schedules','canImport':bool(rows) or body['declaration']=='no_flights' or active})
        return result

    def import_draft(self, airport, service_date, revision, web_version):
        with self.lock:
            info = self.info(airport,service_date)
            if not info['canImport']:
                raise ValueError('No applicable Web data to import')
            if type(web_version) is not int or web_version != info['webVersion']:
                raise DraftConflict('Web data changed. Review it again before importing.')
            if type(revision) is not int:
                raise ValueError('Invalid draft revision')
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                draft, current = db.execute('SELECT draft,draft_revision FROM state WHERE airport=?',(airport,)).fetchone()
                if current != revision:
                    raise DraftConflict('Draft changed. Review it again before importing.')
                rows = json.loads(draft)
                old = db.execute('SELECT flight_ids,service_date,baseline FROM upstream_imports WHERE airport=?',(airport,)).fetchone()
                old_ids = set(json.loads(old[0])) if old else set()
                manual = [row for row in rows if row['id'] not in old_ids]
                existing = {row['id']:row for row in rows if row['id'] in old_ids}
                baseline = {row['id']:row for row in json.loads(old[2])} if old else {}
                imported = []
                for flight in info['flights']:
                    if any(row.get('direction','departure')==flight['direction'] and row['flightNumber']==flight['flightNumber'] for row in manual):
                        raise ValueError('A local flight has the same direction and flight number. Resolve it before importing.')
                    previous = existing.get(flight['id'],{})
                    extras = {key:previous.get(key,flight.get(key,'')) for key in ('airlineLogo','languages')}
                    if old and old[1] == service_date:
                        extras.update({key:previous[key] for key in ('estimatedTime','estimatedDate','actualTime','actualDate','gate','remark') if key in previous and previous[key]!=baseline.get(flight['id'],{}).get(key)})
                    if flight['remark']=='Cancelled':
                        extras['remark']='Cancelled'
                    imported.append({**flight,**extras})
                if len(manual)+len(imported)>100:
                    raise ValueError('Current FIDS limit: 100 flights')
                db.execute('UPDATE state SET draft=?,draft_revision=draft_revision+1 WHERE airport=?',(json.dumps(manual+imported),airport))
                db.execute('INSERT INTO upstream_imports VALUES (?,?,?,?,?) ON CONFLICT(airport) DO UPDATE SET flight_ids=excluded.flight_ids,service_date=excluded.service_date,web_version=excluded.web_version,baseline=excluded.baseline',(airport,json.dumps([row['id'] for row in imported]),service_date,web_version,json.dumps(info['flights'])))
        return info
