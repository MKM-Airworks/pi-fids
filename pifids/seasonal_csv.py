"""Explicit local seasonal imports, separate from authenticated Web releases."""
import csv
import hashlib
import io
import json
import re
from datetime import date
from . import sites
from .store import DraftConflict
from .upstream import project
from .operating_weeks import overlap, validate_weeks

MAX_BYTES=128*1024
COLUMNS=('carrier','number','movement','origin','destination','geo','validFrom','validTo','daysText','time','sta','codeshares','weeksText')
FIELDS=set(COLUMNS)
GUIDE_PREFIX='# '
GUIDE=(
    '# シーズンダイヤCSV / Seasonal schedule CSV',
    '# この案内と空行は読み飛ばします / Guide lines and blank lines before the header are skipped.',
    '# 見出しを残し次の行から入力 / Keep the header and enter schedules beneath it.',
    '# carrier: 航空会社コード / airline code (HB). number: 便番号 / flight number (8235).',
    '# movement: DEP=出発/departure; ARR=到着/arrival. origin/destination: 空港3文字 / airport codes.',
    '# geo: DOM=国内/domestic; INTL=国際/international.',
    '# validFrom/validTo: YYYY-MM-DD. daysText: 1=月/Mon … 7=日/Sun (15=月・金/Mon and Fri).',
    '# time: 出発定刻 / STD; sta: 到着定刻 / STA. HH:MM. codeshares: 便名をセミコロンで区切る / separate flight numbers with semicolons.',
    '# weeksText: 月内の週（日曜始まり・月初を含む週が第1週） / Sunday-start calendar weeks; blank = every week.',
    '# 入力例 / Example: HB,8235,ARR,HKG,ROR,INTL,2026-11-01,2026-11-30,15,,19:45,,135',
    '# 入力例 / Example: HB,8236,DEP,ROR,HKG,INTL,2026-11-01,2026-11-30,3,20:45,,,24',
    '# 日付指定便は開始日と終了日を同じ日に / For a date-specific flight use the same start and end date.',
)


def template():
    buffer=io.StringIO()
    for line in GUIDE:
        buffer.write(line+'\r\n')
    csv.writer(buffer).writerow(COLUMNS)
    return buffer.getvalue().encode('utf-8-sig')


def init_tables(store):
    with store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS local_schedule_cache (airport TEXT PRIMARY KEY,body TEXT NOT NULL,flight_ids TEXT NOT NULL,service_date TEXT NOT NULL,baseline TEXT NOT NULL)')

def parse(text,airport,zone):
    sites.airport_code(airport);sites.timezone_name(zone)
    if not isinstance(text,str) or not 0<len(text.encode('utf-8'))<=MAX_BYTES:raise ValueError('CSV must be UTF-8 and at most 128 KB')
    lines=text.lstrip('\ufeff').splitlines(keepends=True)
    first_data=0
    while first_data<len(lines) and (not lines[first_data].strip() or lines[first_data].startswith(GUIDE_PREFIX)):
        first_data+=1
    reader=csv.DictReader(io.StringIO(''.join(lines[first_data:])),strict=True)
    if not reader.fieldnames or set(reader.fieldnames) not in (FIELDS, FIELDS-{'weeksText'}) or len(set(reader.fieldnames))!=len(reader.fieldnames):raise ValueError('Use the MKM Flight Web seasonal CSV columns')
    flights=[];groups={}
    try:
        for line,row in enumerate(reader,2):
            if len(flights)>=1000 or None in row or any(value is None for value in row.values()):raise ValueError('Invalid CSV row or too many schedules')
            row={key:value.strip() for key,value in row.items()}
            if row['geo'] not in ('','DOM','INTL'):raise ValueError('Geo must be DOM or INTL')
            direction={'DEP':'departure','ARR':'arrival'}.get(row['movement'])
            if not direction:raise ValueError('Movement must be DEP or ARR')
            for key in ('origin','destination'):sites.airport_code(row[key])
            if row['origin' if direction=='departure' else 'destination']!=airport:raise ValueError('CSV airport differs from installation')
            if not re.fullmatch('[A-Z0-9]{2,3}',row['carrier']) or not re.fullmatch('[0-9]{1,5}[A-Z]?',row['number']):raise ValueError('Invalid airline or flight number')
            start=date.fromisoformat(row['validFrom']);end=date.fromisoformat(row['validTo'])
            if start.isoformat()!=row['validFrom'] or end.isoformat()!=row['validTo'] or start>end:raise ValueError('Invalid schedule validity')
            if not re.fullmatch('[1-7]{1,7}',row['daysText']) or len(set(row['daysText']))!=len(row['daysText']):raise ValueError('Operating days must use 1 (Monday) through 7 (Sunday)')
            time=row['time'] if direction=='departure' else row['sta']
            if not re.fullmatch('(?:[01][0-9]|2[0-3]):[0-5][0-9]',time):raise ValueError('Invalid scheduled time')
            days=sorted(map(int,row['daysText']))
            weeks=validate_weeks(row.pop('weeksText',''))
            if weeks:row['weeksText']=weeks
            rule={'operatingDays':days,'weeksText':weeks}
            number=row['carrier']+row['number']
            for prior in groups.get((direction,number),[]):
                first=max(start,date.fromisoformat(prior['validFrom']));last=min(end,date.fromisoformat(prior['validTo']))
                if first<=last and overlap(rule,prior,first,last):raise ValueError('Overlapping schedules for '+number)
            flight={'id':'csv-'+hashlib.sha256(json.dumps(row,sort_keys=True).encode()).hexdigest()[:32],'flightNumber':number,'airlineCode':row['carrier'],'direction':direction,'origin':row['origin'],'destination':row['destination'],'validFrom':row['validFrom'],'validTo':row['validTo'],**rule,'scheduledTime':time,'status':'NA','timeStatus':'','boardingStatus':'','codeshares':row['codeshares'],'geo':row['geo']}
            flights.append(flight);groups.setdefault((direction,number),[]).append(flight)
    except (csv.Error,ValueError) as error:raise ValueError('CSV row '+str(first_data+reader.line_num)+': '+str(error)) from None
    if not flights:raise ValueError('CSV has no schedules')
    return {'organizationId':'local-csv','airportId':airport,'product':'pi-fids','stationAirport':airport,'timezone':zone,'coverage':{'from':min(r['validFrom'] for r in flights),'to':max(r['validTo'] for r in flights)},'flights':flights}

def preview(store,data):
    airport=data.get('airport');store.read(airport)
    body=parse(data.get('csv'),airport,store.timezone(airport))
    flights=project(body,data.get('serviceDate'))
    return {'coverage':body['coverage'],'scheduleCount':len(body['flights']),'flights':flights,'source':'CSV seasonal schedule'}

def import_draft(store,data):
    airport=data.get('airport');store.read(airport);init_tables(store)
    body=parse(data.get('csv'),airport,store.timezone(airport));day=data.get('serviceDate');fresh=project(body,day)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        draft,revision=db.execute('SELECT draft,draft_revision FROM state WHERE airport=?',(airport,)).fetchone()
        if data.get('expectedDraftRevision')!=revision:raise DraftConflict('Draft changed. Review it again before importing.')
        old=db.execute('SELECT flight_ids,service_date,baseline FROM local_schedule_cache WHERE airport=?',(airport,)).fetchone()
        if not old:
            exists=db.execute("SELECT 1 FROM sqlite_master WHERE name='upstream_imports'").fetchone()
            old=db.execute('SELECT flight_ids,service_date,baseline FROM upstream_imports WHERE airport=?',(airport,)).fetchone() if exists else None
        ids=set(json.loads(old[0])) if old else set();rows=json.loads(draft)
        from .daily import carryovers,operation_key
        existing=[r for r in rows if r['id'] in ids]
        by_operation={operation_key(r):r for r in existing}
        baseline={operation_key(r):r for r in json.loads(old[2])} if old else {}
        future_days=sorted({r['serviceDate'] for r in existing if r['serviceDate']>day and body['coverage']['from']<=r['serviceDate']<=body['coverage']['to']})
        for future_day in future_days:
            fresh.extend(row for row in project(body,future_day) if (row['direction'],row['flightNumber'],row['serviceDate']) in by_operation)
        raw_baseline=json.loads(json.dumps(fresh))
        for row in fresh:
            prior=by_operation.get(operation_key(row),{})
            for key in ('airlineLogo','languages'):
                if key in prior:row[key]=prior[key]
            for key in ('estimatedTime','estimatedDate','actualTime','actualDate','gate','belt','remark','codeshareFlights'):
                if key in prior and prior[key]!=baseline.get(operation_key(row),{}).get(key):row[key]=prior[key]
        fresh=carryovers(db,airport,existing,day,store.timezone(airport))+fresh
        manual=[r for r in rows if r['id'] not in ids]
        if {(r['direction'],r['flightNumber'],r['serviceDate']) for r in manual}&{(r['direction'],r['flightNumber'],r['serviceDate']) for r in fresh}:raise DraftConflict('A local flight conflicts with the CSV schedule')
        if len(manual)+len(fresh)>100:raise ValueError('Current FIDS limit: 100 flights')
        db.execute('INSERT INTO local_schedule_cache VALUES (?,?,?,?,?) ON CONFLICT(airport) DO UPDATE SET body=excluded.body,flight_ids=excluded.flight_ids,service_date=excluded.service_date,baseline=excluded.baseline',(airport,json.dumps(body),json.dumps([r['id'] for r in fresh]),day,json.dumps(raw_baseline)))
        db.execute('UPDATE state SET draft=?,draft_revision=draft_revision+1 WHERE airport=?',(json.dumps(manual+fresh),airport))
        store.audit(db,airport,'schedule.csv-import',day,rows,manual+fresh,source='CSV seasonal schedule')
    return {'ok':True,'scheduleCount':len(body['flights']),'flightCount':len(fresh)}
