"""Waiting for a charger is not slow engine search."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from training import large_run


class DatagenTiming(unittest.TestCase):
    def test_long_power_pause_does_not_dilute_active_rate(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"run"
            binary=Path(d)/"producer"
            binary.write_bytes(b"fixture")
            now=[0.0]
            pauses=iter([600,3600])
            def wait(*_):
                now[0]+=next(pauses)
            def run(argv,**_):
                path=Path(argv[2])
                path.mkdir()
                meta=dict(games=1,positions=20,mode="mero7",seed=int(argv[6]),nodes=5000,
                          opening_plies=8,format="bulletformat-chessboard-v1")
                (path/"COMPLETE.json").write_text(json.dumps(meta))
                (path/"positions.bullet").write_bytes(bytes(32*20))
                (path/"games.tsv").touch()
                now[0]+=2
            with (patch.object(large_run,"await_power",side_effect=wait),
                  patch.object(large_run.time,"monotonic",side_effect=lambda:now[0]),
                  patch.object(large_run.subprocess,"run",side_effect=run),redirect_stdout(io.StringIO())):
                large_run.generate(binary,root,target=40,games_per_shard=1,workers=1,seed=11)
            result=json.loads((root/"progress.json").read_text())
            self.assertEqual(result["positions_per_second"],10)
            self.assertEqual(result["sealed_shards"],2)
