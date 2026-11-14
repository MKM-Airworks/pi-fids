"""Local multilingual airline directory; upstream codes remain unchanged."""
import json
import re

LANGUAGES=('ja','en')
DEFAULTS={}
def validate(value):
    if not isinstance(value,dict) or len(value)>200:raise ValueError('Invalid airline directory')
    result={}
    for code,names in value.items():
        if not isinstance(code,str) or not re.fullmatch('[A-Z0-9]{2,3}',code) or not isinstance(names,dict) or set(names)-set((*LANGUAGES,'logo')):raise ValueError('Invalid airline code or language')
        clean={}
        logo=names.get('logo','')
        if not isinstance(logo,str) or (logo and not re.fullmatch('[a-f0-9]{64}',logo)):raise ValueError('Invalid airline logo')
        for language,name in names.items():
            if language=='logo':continue
            if not isinstance(name,str) or len(name)>80 or any(ord(c)<32 for c in name):raise ValueError('Invalid airline name')
            clean[language]=name.strip()
        if not any(clean.values()):raise ValueError('Airline name required')
        if logo:clean['logo']=logo
        result[code]=clean
    return result
def read(db,airport):
    row=db.execute('SELECT body FROM airline_names WHERE airport=?',(airport,)).fetchone()
    return json.loads(row[0]) if row else DEFAULTS.copy()
def write(db,airport,value):
    db.execute('INSERT INTO airline_names VALUES (?,?) ON CONFLICT(airport) DO UPDATE SET body=excluded.body',(airport,json.dumps(value,ensure_ascii=False)))
