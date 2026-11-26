import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from training.large_run import check_shard,shard_seed
from training.scale_fixture import fixture
from training.screlu_wire import counts,unpack,STANDALONE_MAGIC,width_of
from scripts.fresh_openings import verify

class ScaleContracts(unittest.TestCase):
    def test_new_widths_are_explicit_and_checksummed(self):
        for width in (256,384):
            blob=fixture(width)
            self.assertEqual(blob[:8],STANDALONE_MAGIC)
            self.assertEqual(width_of(blob),width)
            self.assertEqual(tuple(map(len,unpack(blob))),counts(width))
            with self.assertRaises(ValueError):
                unpack(blob[:-1])
            with self.assertRaises(ValueError):
                unpack(b"MRSCREL1"+blob[8:])

    def test_incomplete_and_wrong_teacher_shards_dont_count(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);cfg=dict(seed=17,games_per_shard=2,nodes=5000)
            m=dict(format="bulletformat-chessboard-v1",mode="mero7",seed=shard_seed(17,0),
                   nodes=5000,opening_plies=8,games=2,positions=1)
            (p/"COMPLETE.json").write_text(json.dumps(m)); (p/"games.tsv").touch()
            (p/"positions.bullet").write_bytes(bytes(31))
            with self.assertRaises(ValueError):check_shard(p,cfg,0)
            m["mode"]="hce";(p/"COMPLETE.json").write_text(json.dumps(m))
            (p/"positions.bullet").write_bytes(bytes(32))
            with self.assertRaises(ValueError):check_shard(p,cfg,0)
            self.assertNotEqual(shard_seed(17,0),shard_seed(17,1))

    @unittest.skipUnless(importlib.util.find_spec("numpy"),"optional split dependency")
    def test_color_flip_is_an_involution(self):
        from training.large_split import flipped_layout
        p=Path("training/data/selfplay-pilot-v1/positions.bullet")
        with p.open("rb") as f:
            for _ in range(128):
                layout=f.read(32)[:24]
                self.assertEqual(flipped_layout(flipped_layout(layout)),layout)

    def test_book_rejects_repeated_positions(self):
        from training.large_run import sha
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"x.epd"; p.write_text("x\nx\n")
            (p.with_suffix(".json")).write_text(json.dumps(dict(format="fresh-8ply-v1",sha256=sha(p),pairs=2)))
            with self.assertRaises(ValueError):verify(p)

    @unittest.skipUnless(importlib.util.find_spec("numpy"),"optional split dependency")
    def test_qualification_panels_share_no_training_features(self):
        from training.large_split import panel_layouts,flipped_layout
        from training.probe_material import PANEL
        excluded=panel_layouts()
        self.assertGreater(len(excluded),1000)
        self.assertTrue(all(flipped_layout(x) in excluded for x in excluded))
        # Original layouts appear in the historical file; counterfactuals do not
        # need an artificial score or an evaluation label to be held out.
        data=PANEL.read_bytes()
        self.assertGreaterEqual(sum(data[i:i+24] in excluded for i in range(0,len(data),32)),256)
