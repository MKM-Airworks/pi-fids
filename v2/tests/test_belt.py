import tempfile,unittest
from pathlib import Path
from pifids.store import Store,validate
from pifids import board_config
from pifids.upstream import project
from pifids.seasonal_csv import parse
from test_seasonal_csv import CSV
class BeltTests(unittest.TestCase):
 def test_edit_publish_clear(self):
  with tempfile.TemporaryDirectory() as tmp:
   s=Store(Path(tmp)/'db');data=dict(airport='ROR',flightNumber='UA143',destination='GUM',time='21:40',direction='arrival',belt='2')
   s.add(data);s.publish('ROR');state=s.read('ROR');self.assertEqual(state['flights'][0]['belt'],'2')
   s.change_flight({**data,'id':state['draft'][0]['id'],'belt':'','expectedDraftRevision':state['draftRevision']});s.publish('ROR');self.assertEqual(s.read('ROR')['flights'][0]['belt'],'')
   with self.assertRaises(ValueError):validate({**data,'belt':'x'*21})
 def test_project_and_terminal_columns(self):
  body=parse(CSV,'ROR','Pacific/Palau')
  for f in body['flights']:f['belt']='3'
  self.assertTrue(all(f['belt']=='3' for f in project(body,'2026-10-11')))
  self.assertNotIn('belt',board_config.validate({'direction':'arrival'})['arrivalColumns'])
  self.assertEqual(board_config.validate({'direction':'arrival','arrivalColumns':['flight','belt']})['arrivalColumns'],['flight','belt'])
  with self.assertRaises(ValueError):board_config.validate({'direction':'departure','departureColumns':['belt']})
