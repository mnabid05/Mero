import importlib.util
import tempfile
import unittest
from pathlib import Path
from training.split_selfplay import split_shard

class PilotSplitTests(unittest.TestCase):
    def test_shard_size_limit_before_read(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/"COMPLETE.json").write_text('{"positions":50000000}')
            with self.assertRaisesRegex(ValueError,"oversized"):
                split_shard(p,p/"split",1)

@unittest.skipUnless(importlib.util.find_spec("torch"),"optional training dependencies")
class BulletImportTests(unittest.TestCase):
    def test_orientation_and_padding(self):
        import numpy as np
        from training.import_bullet import convert
        from training.screlu_wire import COUNTS,unpack
        raw=np.zeros(sum(COUNTS),dtype="<i2")
        raw[0]=77
        payload=raw.tobytes()
        pad=(b"bullet"*11)[:(-len(payload))%64]
        ft,*_=unpack(convert(payload+pad))
        self.assertEqual(ft[56*512],77)
        self.assertEqual(ft[0],0)
        with self.assertRaisesRegex(ValueError,"padding"):
            convert(payload+bytes(len(pad)))

    def test_pair_features_match_fen_reference(self):
        import struct
        from training.import_bullet import prepare
        from training.screlu_data import encode
        # Bullet's normalized mover has K e1 and P b2; opponent has k e8.
        occ=(1<<4)|(1<<9)|(1<<60)
        blob=struct.pack("<Q16shBBB3s",occ,bytes([5,13])+bytes(14),-91,0,4,4,bytes(3))
        a,b,cp,wdl=prepare(blob)
        for fen in ("4k3/8/8/8/8/8/1P6/4K3 w - - 0 1",
                    "4k3/1p6/8/8/8/8/8/4K3 b - - 0 1"):
            (ours,theirs),_,_=encode(fen)
            self.assertEqual(sorted(a[0].tolist()),sorted(ours))
            self.assertEqual(sorted(b[0].tolist()),sorted(theirs))
        self.assertEqual((cp[0],wdl[0]),(-91,0))
