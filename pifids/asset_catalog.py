"""Registered image browsing and deletion without breaking live references."""
import json
import re
from .image_metadata import dimensions
from . import airline_names


def usage(db, airport, digest):
    refs=[]
    exists=lambda table:db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone()
    def add(kind,name,field):refs.append({'kind':kind,'name':name,'field':field})
    row=db.execute('SELECT draft,published FROM state WHERE airport=?',(airport,)).fetchone()
    if row:
        for category,body in zip(('draft','published'),row):
            for flight in json.loads(body):
                if flight.get('airlineLogo')==digest:add(category,flight['flightNumber']+' · '+flight.get('serviceDate',''),'logo')
    for code,names in airline_names.read(db,airport).items():
        if names.get('logo')==digest:add('airline',code,'logo')
    for display,logo,image in db.execute('SELECT display_id,logo,image FROM display_assets WHERE airport=?',(airport,)):
        for field,value in (('logo',logo),('image',image)):
            if value==digest:add('terminal',display,field)
    for table,fields in (('signage_settings',('defaultImage',)),('board_settings',('logo',))):
        for display,body in db.execute('SELECT display_id,body FROM '+table+' WHERE airport=?',(airport,)):
            data=json.loads(body)
            for field in fields:
                if data.get(field)==digest:add('terminal',display,field)
    if exists('signage_profiles'):
        for name,logo,image in db.execute('SELECT name,logo,image FROM signage_profiles WHERE airport=?',(airport,)):
            for field,value in (('logo',logo),('image',image)):
                if value==digest:add('profile',name,field)
    return refs


def catalog(store, airport):
    store.read(airport)
    with store.connect() as db:
        result=[]
        for digest,name,mime,body,kind in db.execute('SELECT a.digest,a.name,a.mime,a.body,k.kind FROM assets a LEFT JOIN asset_kinds k ON k.airport=a.airport AND k.digest=a.digest WHERE a.airport=? ORDER BY a.name,a.digest',(airport,)):
            refs=usage(db,airport,digest);size=dimensions(body)
            result.append({'digest':digest,'name':name,'mime':mime,'kind':kind or 'legacy','bytes':len(body),'width':size[0] if size else None,'height':size[1] if size else None,'usage':refs,'canDelete':not refs})
        result.insert(0,{'digest':'builtin-default','name':'MKM Airworks','kind':'default','builtin':True,'usage':[],'canDelete':False})
        return result


def delete(store, data):
    airport,digest=data.get('airport'),data.get('digest');store.read(airport)
    if not isinstance(digest,str) or not re.fullmatch('[a-f0-9]{64}',digest):raise ValueError('Invalid image ID')
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT name FROM assets WHERE airport=? AND digest=?',(airport,digest)).fetchone()
        if not row:raise ValueError('Image not found for airport')
        if usage(db,airport,digest):raise ValueError('Image is in use. Remove its assignments before deleting it.')
        db.execute('DELETE FROM asset_kinds WHERE airport=? AND digest=?',(airport,digest))
        db.execute('DELETE FROM assets WHERE airport=? AND digest=?',(airport,digest))
        store.audit(db,airport,'asset.delete',digest,{'name':row[0]},None)
    return {'ok':True}
