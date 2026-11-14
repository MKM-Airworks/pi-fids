"""Local multilingual airport directory; upstream codes remain unchanged."""
import json
import re

LANGUAGES=('ja','en','zh-Hans','zh-Hant','ko')
DEFAULTS={
 'HND':dict(zip(LANGUAGES,('東京（羽田）','Tokyo (Haneda)','东京（羽田）','東京（羽田）','도쿄 (하네다)'))),
 'UKB':dict(zip(LANGUAGES,('神戸','Kobe','神户','神戶','고베'))),
 'FUK':dict(zip(LANGUAGES,('福岡','Fukuoka','福冈','福岡','후쿠오카'))),
 'OKA':dict(zip(LANGUAGES,('那覇','Naha','那霸','那霸','나하'))),
 'SHI':dict(zip(LANGUAGES,('下地島','Shimojishima','下地岛','下地島','시모지시마'))),
 'ROR':dict(zip(LANGUAGES,('パラオ','Palau','帕劳','帛琉','팔라우'))),
}
def validate(value):
    if not isinstance(value,dict) or len(value)>200:raise ValueError('Invalid airport directory')
    result={}
    for code,names in value.items():
        if not isinstance(code,str) or not re.fullmatch('[A-Z]{3}',code) or not isinstance(names,dict) or set(names)-set(LANGUAGES):raise ValueError('Invalid airport code or language')
        clean={}
        for language,name in names.items():
            if not isinstance(name,str) or len(name)>80 or any(ord(c)<32 for c in name):raise ValueError('Invalid airport name')
            clean[language]=name.strip()
        if not any(clean.values()):raise ValueError('Airport name required')
        result[code]=clean
    return result
def read(db,airport):
    row=db.execute('SELECT body FROM airport_names WHERE airport=?',(airport,)).fetchone()
    return json.loads(row[0]) if row else DEFAULTS.copy()
def write(db,airport,value):
    db.execute('INSERT INTO airport_names VALUES (?,?) ON CONFLICT(airport) DO UPDATE SET body=excluded.body',(airport,json.dumps(value,ensure_ascii=False)))
