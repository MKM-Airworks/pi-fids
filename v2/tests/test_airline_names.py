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
 def test_logo_is_validated_delivered_and_cached(self):
  import base64
  from test_assets import png
  with tempfile.TemporaryDirectory() as d:
   s=Store(Path(d)/'m.db');image=png();digest=s.upload_asset({'airport':'SHI','name':'ANA logo','kind':'logo','body':base64.b64encode(image).decode()})
   s.save_airline_name({'airport':'SHI','code':'NH','names':{'ja':'全日本空輸','en':'ANA','logo':digest}})
   f=s.feed('SHI','default');r=ReceiverStore(Path(d)/'r.db');r.accept('SHI','default',f,f['control'],{digest:image})
   r=ReceiverStore(Path(d)/'r.db');self.assertEqual(r.read('SHI')['airlineNames']['NH']['logo'],digest);self.assertEqual(r.asset('SHI',digest)[1],image)
   with self.assertRaises(ValueError):s.save_airline_name({'airport':'ROR','code':'NH','names':{'en':'ANA','logo':digest}})
   with self.assertRaises(ValueError):s.save_airline_name({'airport':'SHI','code':'NH','names':{'en':'ANA','logo':'invalid'}})
