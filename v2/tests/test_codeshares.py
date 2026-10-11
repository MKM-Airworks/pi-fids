import json,tempfile,unittest
from pathlib import Path
from pifids.store import Store,validate
from pifids import board_config
from pifids.seasonal_csv import parse
from pifids.upstream import project
from test_seasonal_csv import CSV
class CodeshareTests(unittest.TestCase):
 def test_edit_add_change_remove_and_publish(self):
  with tempfile.TemporaryDirectory() as tmp:
   s=Store(Path(tmp)/'manager.sqlite');data=dict(airport='ROR',flightNumber='UA142',destination='NRT',time='20:00',serviceDate='2026-10-11',codeshares='nh6467, UA142, NH6467')
   s.add(data);state=s.read('ROR');row=state['draft'][0];self.assertEqual(row['codeshareFlights'],['NH6467']);s.publish('ROR')
   s.change_flight({**data,'id':row['id'],'expectedDraftRevision':state['draftRevision'],'codeshares':'NH6468, PR999'})
   self.assertEqual(s.read('ROR')['draft'][0]['codeshareFlights'],['NH6468','PR999']);self.assertEqual(s.read('ROR')['flights'][0]['codeshareFlights'],['NH6467'])
   state=s.read('ROR');s.change_flight({**data,'id':row['id'],'expectedDraftRevision':state['draftRevision'],'codeshares':''});s.publish('ROR')
   self.assertEqual(s.read('ROR')['flights'][0]['codeshareFlights'],[])
 def test_csv_and_web_projection(self):
  body=parse(CSV.replace('02:05,,','02:05,,NH6467'),'ROR','Pacific/Palau')
  self.assertEqual(next(r for r in project(body,'2026-10-11') if r['direction']=='departure')['codeshareFlights'],['NH6467'])
  body['flights'][0]['codeshareFlights']=['NH6467','PR999'];self.assertEqual(next(r for r in project(body,'2026-10-11') if r['direction']=='departure')['codeshareFlights'],['NH6467','PR999'])
 def test_validation_and_terminal_options(self):
  data=dict(airport='ROR',flightNumber='UA142',destination='NRT',time='20:00')
  for bad in [None,{},['BAD'],['NH6467']*31]:
   with self.assertRaises(ValueError):validate({**data,'codeshareFlights':bad})
  for bad in [{'codeshareEnabled':'yes'},{'codeshareInterval':2},{'codeshareInterval':True},{'codeshareInterval':61}]:
   with self.assertRaises(ValueError):board_config.validate({'direction':'departure',**bad})
  config=board_config.validate(dict(direction='departure',codeshareEnabled=False,codeshareInterval=7));self.assertFalse(config['codeshareEnabled']);self.assertEqual(config['codeshareInterval'],7)

 def test_removed_imported_codeshares_stay_removed_on_daily_and_reimport(self):
  from pifids.seasonal_csv import import_draft
  from pifids.daily import DailySchedules
  from datetime import datetime
  with tempfile.TemporaryDirectory() as tmp:
   s=Store(Path(tmp)/'manager.sqlite');s.configure_site('ROR','Pacific/Palau');csv=CSV.replace('02:05,,','02:05,,NH6467')
   data=dict(airport='ROR',csv=csv,serviceDate='2026-10-11',expectedDraftRevision=s.read('ROR')['draftRevision']);import_draft(s,data);s.publish('ROR')
   state=s.read('ROR');f=next(f for f in state['draft'] if f['direction']=='departure');s.change_flight({**f,'codeshareFlights':[],'expectedDraftRevision':state['draftRevision']});s.publish('ROR')
   DailySchedules(s).step(datetime.fromisoformat('2026-10-11T00:00:00+09:00'))
   self.assertEqual(next(f for f in s.read('ROR')['flights'] if f['direction']=='departure')['codeshareFlights'],[])
   import_draft(s,{**data,'expectedDraftRevision':s.read('ROR')['draftRevision']})
   self.assertEqual(next(f for f in s.read('ROR')['draft'] if f['direction']=='departure')['codeshareFlights'],[])
