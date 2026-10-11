import json
import re
COLUMNS=('scheduled','estimated','destination','airline','flight','gate','remark','belt')

def validate(data):
    if data is None:return None
    if not isinstance(data,dict) or data.get('direction') not in ('departure','arrival'):
        raise ValueError('Select departure or arrival')
    result={'direction':data['direction']}
    for key,default,choices in [('traffic','all',('all','domestic','international')),('orientation','landscape',('landscape','portrait'))]:
        value=data.get(key,default)
        if value not in choices:raise ValueError('Invalid '+key+' display setting')
        if key in data:result[key]=value
    for key in ('departureColumns','arrivalColumns'):
        columns=data.get(key,list(COLUMNS[:-1]))
        if not isinstance(columns,list) or not columns or any(x not in COLUMNS or (key=='departureColumns' and x=='belt') for x in columns) or len(set(columns))!=len(columns):
            raise ValueError('Select at least one valid display column')
        result[key]=[x for x in COLUMNS if x in columns]
    logo=data.get('logo','')
    if not isinstance(logo,str) or (logo and not re.fullmatch('[a-f0-9]{64}',logo)):raise ValueError('Invalid board logo')
    languages=data.get('languages',['en','ja'])
    if not isinstance(languages,list) or not languages or any(x not in ('en','ja','zh-Hans','zh-Hant','ko') for x in languages) or len(set(languages))!=len(languages):raise ValueError('Select unique terminal languages in display order')
    interval=data.get('languageInterval',8)
    if type(interval) is not int or not 3<=interval<=60:raise ValueError('Language interval must be 3 to 60 seconds')
    result['languages']=languages
    result['languageInterval']=interval
    if 'codeshareEnabled' in data:
        if type(data['codeshareEnabled']) is not bool:raise ValueError('Invalid codeshare display setting')
        result['codeshareEnabled']=data['codeshareEnabled']
    if 'codeshareInterval' in data:
        interval=data['codeshareInterval']
        if type(interval) is not int or not 3<=interval<=60:raise ValueError('Codeshare interval must be 3 to 60 seconds')
        result['codeshareInterval']=interval
    for key in ('departureShowMinutes','arrivalShowMinutes'):
        if key in data:
            value=data[key]
            if value is not None and (type(value) is not int or not 0<=value<=10080):raise ValueError('Display start must be 0 to 10080 minutes or blank')
            result[key]=value
    result['logo']=logo
    return result

def read(db,airport,display_id):
    row=db.execute('SELECT body FROM board_settings WHERE airport=? AND display_id=?',(airport,display_id)).fetchone()
    return validate(json.loads(row[0])) if row else None

def write(db,airport,display_id,data):
    if data is None:
        db.execute('DELETE FROM board_settings WHERE airport=? AND display_id=?',(airport,display_id))
    else:
        db.execute('INSERT INTO board_settings VALUES (?,?,?) ON CONFLICT(airport,display_id) DO UPDATE SET body=excluded.body',(airport,display_id,json.dumps(validate(data))))
