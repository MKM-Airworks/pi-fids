"""Render-only administrator overrides for saved seasonal schedules."""
import hashlib
import json
from datetime import date, timedelta

from pifids.seasonal_csv import init_tables
from pifids.store import DraftConflict
from pifids.upstream import SCOPE, contract, local_date, project, schema_check, verify

FIELDS = ('flightNumber', 'origin', 'destination', 'validFrom', 'validTo',
          'operatingDays', 'scheduledTime')


class SeasonalEditor:
    def __init__(self, store, airport, upstream):
        self.store, self.airport, self.upstream = store, airport, upstream
        init_tables(store)
        with store.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS demo_seasonal_edits (
                source TEXT NOT NULL, flight_id TEXT NOT NULL, effective TEXT NOT NULL,
                base TEXT NOT NULL, changes TEXT NOT NULL,
                PRIMARY KEY (source, flight_id, effective))""")

    def source_body(self, db):
        csv = db.execute('SELECT body FROM local_schedule_cache WHERE airport=?',
                         (self.airport,)).fetchone()
        if csv:
            return 'CSV', json.loads(csv[0])
        cached = db.execute('SELECT manifest,body FROM upstream_cache WHERE airport=?',
                            (self.airport,)).fetchone()
        if not cached:
            raise ValueError('シーズンダイヤを先に取り込んでください。')
        return 'MKM Flight Web', verify(json.loads(cached[0]), cached[1],
                                        self.upstream.require_airport(self.airport))

    def merged(self, db, source, body, day, strict=True):
        edits = {}
        for key, base, changes in db.execute(
            'SELECT flight_id,base,changes FROM demo_seasonal_edits '
            'WHERE source=? AND effective<=? ORDER BY effective', (source, day)
        ):
            edits[key] = (json.loads(base), json.loads(changes))
        flights, conflicts = [], []
        for flight in body['flights']:
            base, changes = edits.pop(flight['id'], ({}, {}))
            conflict = any(flight.get(key) not in (base.get(key), value)
                           for key, value in changes.items())
            if conflict:
                conflicts.append(flight['id'])
            flights.append({**flight, **changes})
        conflicts.extend(edits)
        if strict and conflicts:
            raise DraftConflict('配信元の変更と競合しています。管理者がシーズンダイヤを確認してください。')
        return {**body, 'flights': flights}, conflicts

    def for_rollover(self, db, body, day, csv):
        source = 'CSV' if csv else 'MKM Flight Web'
        return self.merged(db, source, body, day)[0]

    def _day(self):
        return (local_date(self.store.timezone(self.airport)) + timedelta(days=1)).isoformat()

    def _state(self, db):
        source, original = self.source_body(db)
        day = self._day()
        merged, conflicts = self.merged(db, source, original, day, strict=False)
        revision = hashlib.sha256(json.dumps(
            [original, merged, conflicts, day], sort_keys=True).encode()).hexdigest()
        return source, original, merged, day, conflicts, revision

    def listing(self):
        with self.store.connect() as db:
            source, original, merged, day, conflicts, revision = self._state(db)
        return dict(source=source, effective=day, coverage=original['coverage'],
                    conflicts=conflicts, revision=revision, flights=merged['flights'])

    def change(self, data, *, save):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            source, original, merged, day, conflicts, revision = self._state(db)
            if data.get('revision') != revision:
                raise DraftConflict('ダイヤが変更されました。再読み込みしてください。')
            key = data.get('id')
            flight = next((r for r in original['flights'] if r['id'] == key), None)
            prior = next((r for r in merged['flights'] if r['id'] == key), None)
            fields = data.get('fields')
            if flight is None or not isinstance(fields, dict) or set(fields) != set(FIELDS):
                raise ValueError('編集する便と項目を確認してください。')
            changed = {**flight, **fields}
            item_schema = contract({'product': 'pi-fids'}, 'release')['properties']['flights']['items']
            for field, value in fields.items():
                schema_check(value, item_schema['properties'][field])
            if (not changed['flightNumber'].startswith(flight['airlineCode'])
                    or changed['origin' if flight['direction']=='departure' else 'destination'] != self.airport
                    or not original['coverage']['from'] <= changed['validFrom'] <= changed['validTo'] <= original['coverage']['to']):
                raise ValueError('航空会社コード、空港またはダイヤの有効期間を確認してください。')
            for other in merged['flights']:
                if other['id'] == key or (other['flightNumber'], other['direction']) != (changed['flightNumber'], changed['direction']):
                    continue
                start = date.fromisoformat(max(other['validFrom'], changed['validFrom']))
                end = date.fromisoformat(min(other['validTo'], changed['validTo']))
                shared = set(changed['operatingDays']) & set(other['operatingDays'])
                if any((start+timedelta(days=i)).isoweekday() in shared
                       for i in range(min(7, (end-start).days+1))):
                    raise ValueError('同一便の運航日が重複しています。')
            candidate = {**merged, 'flights': [changed if r['id']==key else r for r in merged['flights']]}
            preview_date = data.get('serviceDate')
            if not isinstance(preview_date, str) or preview_date < day:
                raise ValueError('プレビュー日は適用開始日以降を指定してください。')
            rows = project(candidate, preview_date)
            if save:
                changes = {k:v for k,v in fields.items() if v != flight[k]}
                db.execute('INSERT OR REPLACE INTO demo_seasonal_edits VALUES (?,?,?,?,?)',
                           (source, key, day, json.dumps(flight), json.dumps(changes)))
                self.store.audit(db, self.airport, 'schedule.seasonal-edit',
                                 flight['flightNumber'], prior,
                                 {'effective':day, 'flight':changed}, source=source)
            return dict(flights=rows, effective=day)
