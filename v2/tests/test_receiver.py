import hashlib
import tempfile
import unittest
from pathlib import Path
from pifids.receiver import ReceiverStore
from test_assets import png


class ReceiverTests(unittest.TestCase):
    def test_restart_restore_and_failed_update_keeps_visible_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'receiver.sqlite'
            store=ReceiverStore(path)
            digest=hashlib.sha256(png()).hexdigest()
            state={'airport':'ROR','version':1,'flights':[{'airport':'ROR','flightNumber':'TEST1','destination':'Guam','time':'10:00'}]}
            control={'displayId':'gate-01','mode':'gate','airline':'Sample','logo':digest,'image':'','version':1}
            store.accept('ROR','gate-01',state,control,{digest:png()})
            restored=ReceiverStore(path)
            self.assertEqual(restored.read('ROR')['flights'][0]['flightNumber'],'TEST1')
            self.assertEqual(restored.asset('ROR',digest)[1],png())
            for new_state,new_control,images in ((dict(state,version=2),dict(control,image='0'*64,version=2),{'0'*64:b'bad'}),(dict(state,version=0),control,{}),(dict(state,airport='SHI'),control,{})):
                with self.assertRaises(ValueError):
                    restored.accept('ROR','gate-01',new_state,new_control,images)
                self.assertEqual(restored.read('ROR')['version'],1)
                self.assertEqual(restored.display('ROR','gate-01')['image'],'')
            self.assertEqual(restored.read('ROR')['draft'],[])
