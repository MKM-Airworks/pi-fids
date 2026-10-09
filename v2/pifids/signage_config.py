"""Per-terminal fallback image and local-time signage window."""
import json
import re
from datetime import date


def validate(value=None):
    value={} if value is None else value
    if not isinstance(value,dict):raise ValueError('Invalid signage settings')
    result={key:value.get(key,'') for key in ('defaultImage','start','end','date')}
    if any(not isinstance(v,str) for v in result.values()):raise ValueError('Invalid signage settings')
    if result['defaultImage'] and not re.fullmatch(r'[a-f0-9]{64}',result['defaultImage']):raise ValueError('Invalid default image')
    start,end=result['start'],result['end']
    if bool(start)!=bool(end):raise ValueError('Enter both start and end times')
    for t in (start,end):
        if t and not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]',t):raise ValueError('Enter times as HH:MM')
    if start and start==end:raise ValueError('Start and end times must differ')
    if result['date']:
        if not start:raise ValueError('A date requires a time window')
        try:
            if date.fromisoformat(result['date']).isoformat()!=result['date']:raise ValueError()
        except ValueError:raise ValueError('Invalid display date')
    result['enabled']=value.get('enabled',False)
    if type(result['enabled']) is not bool:raise ValueError('Invalid signage purpose')
    return result


def read(db,airport,display_id):
    row=db.execute('SELECT body FROM signage_settings WHERE airport=? AND display_id=?',(airport,display_id)).fetchone()
    return validate(json.loads(row[0]) if row else None)


def write(db,airport,display_id,value):
    value=validate(value)
    db.execute('INSERT INTO signage_settings VALUES (?,?,?) ON CONFLICT(airport,display_id) DO UPDATE SET body=excluded.body',(airport,display_id,json.dumps(value)))
