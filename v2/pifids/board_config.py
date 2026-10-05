import json
import re
COLUMNS=('scheduled','estimated','destination','airline','flight','gate','remark')

def validate(data):
    if data is None:return None
    if not isinstance(data,dict) or data.get('direction') not in ('departure','arrival'):
        raise ValueError('Select departure or arrival')
    result={'direction':data['direction']}
    for key in ('departureColumns','arrivalColumns'):
        columns=data.get(key,list(COLUMNS))
        if not isinstance(columns,list) or not columns or any(x not in COLUMNS for x in columns) or len(set(columns))!=len(columns):
            raise ValueError('Select at least one valid display column')
        result[key]=[x for x in COLUMNS if x in columns]
    logo=data.get('logo','')
    if not isinstance(logo,str) or (logo and not re.fullmatch('[a-f0-9]{64}',logo)):raise ValueError('Invalid board logo')
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
