import tempfile, unittest
from pathlib import Path
from pifids.store import Store
from pifids.receiver import ReceiverStore
class AirlineNameTests(unittest.TestCase):
 def test_directory_delivery_restart_and_isolation(self):
  with tempfile.TemporaryDirectory() as d:
   s=Store(Path(d)/'m.db');s.save_airline_name({'airport':'SHI','code':'nh','names':{'ja':'全日本空輸','en':'All Nippon Airways'}})
   s.save_airline_name({'airport':'SHI','code':'ANA','names':{'ja':'全日本空輸','en':'All Nippon Airways'}})
   f=s.feed('SHI','default');r=ReceiverStore(Path(d)/'r.db');r.accept('SHI','default',f,f['control'],{})
   self.assertEqual(ReceiverStore(Path(d)/'r.db').read('SHI')['airlineNames']['NH']['ja'],'全日本空輸')
   self.assertEqual(s.read('ROR')['airlineNames'],{})
   f['airlineNames']={'!':{'en':'Bad'}}
   with self.assertRaises(ValueError):r.accept('SHI','default',f,f['control'],{})
   self.assertEqual(r.read('SHI')['airlineNames']['ANA']['en'],'All Nippon Airways')
