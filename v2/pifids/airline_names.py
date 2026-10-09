"""Local multilingual airline directory; upstream codes remain unchanged."""
import json
import re

LANGUAGES=('ja','en')
DEFAULTS={}
def validate(value):
    if not isinstance(value,dict) or len(value)>200:raise ValueError('Invalid airline directory')
    result={}
    for code,names in value.items():
        if not isinstance(code,str) or not re.fullmatch('[A-Z0-9]{2,3}',code) or not isinstance(names,dict) or set(names)-set(LANGUAGES):raise ValueError('Invalid airline code or language')
        clean={}
        for language,name in names.items():
            if not isinstance(name,str) or len(name)>80 or any(ord(c)<32 for c in name):raise ValueError('Invalid airline name')
            clean[language]=name.strip()
        if not any(clean.values()):raise ValueError('Airport name required')
        result[code]=clean
    return result
def read(db,airport):
    row=db.execute('SELECT body FROM airline_names WHERE airport=?',(airport,)).fetchone()
    return json.loads(row[0]) if row else DEFAULTS.copy()
def write(db,airport,value):
    db.execute('INSERT INTO airline_names VALUES (?,?) ON CONFLICT(airport) DO UPDATE SET body=excluded.body',(airport,json.dumps(value,ensure_ascii=False)))
