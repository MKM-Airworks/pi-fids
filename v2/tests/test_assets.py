import base64
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from pifids.store import Store


def png():
    def chunk(kind, body):
        return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(b'\x00\x10\x60\xa0')) + chunk(b'IEND', b'')


class AssetTests(unittest.TestCase):
    def test_asset_is_immutable_scoped_and_persistent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'db.sqlite'
            store = Store(path)
            data = {'airport':'ROR', 'name':'logo.png', 'body':base64.b64encode(png()).decode()}
            digest = store.upload_asset(data)
            self.assertEqual(store.upload_asset(data), digest)
            self.assertEqual(len(store.assets('ROR')), 1)
            self.assertEqual(Store(path).asset('ROR', digest), ('image/png', png()))
            with self.assertRaises(ValueError):
                store.asset('SHI', digest)
            store.set_display({'airport':'ROR','displayId':'gate-01','mode':'gate','airline':'Sample','logo':digest})
            self.assertEqual(store.display('ROR','gate-01')['logo'], digest)
            with self.assertRaises(ValueError):
                store.set_display({'airport':'ROR','displayId':'gate-01','mode':'gate','airline':'Sample','logo':'0'*64})
            self.assertEqual(store.display('ROR','gate-01')['version'], 1)

    def test_bad_uploads_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'db.sqlite')
            for body in ('!!!', base64.b64encode(b'<svg></svg>').decode(), base64.b64encode(b'x'*(2*1024*1024+1)).decode()):
                with self.assertRaises(ValueError):
                    store.upload_asset({'airport':'SHI','name':'bad','body':body})
            self.assertEqual(store.assets('SHI'), [])
