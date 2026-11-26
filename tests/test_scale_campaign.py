import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts import scale_campaign as campaign
from scripts.fresh_openings import verify
from scripts.scale_bench import SUITE,SUITE_HASH
from training.large_run import sha


class CampaignGates(unittest.TestCase):
    def test_active_writer_excludes_training_and_matches(self):
        with tempfile.TemporaryDirectory() as d:
            with campaign.machine_slot(Path(d)):
                with self.assertRaisesRegex(RuntimeError,"active"):
                    with campaign.machine_slot(Path(d)):
                        self.fail("acquired twice")
            with campaign.machine_slot(Path(d)):
                pass

    def test_twenty_million_gate_checks_real_frozen_split(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"mero20m-01"
            root.mkdir()
            cfg=dict(schema=1,producer=campaign.PINS["teacher_sha256"],seed=2026112601,
                     games_per_shard=256,nodes=5000,source="Mero 7")
            (root/"campaign.json").write_text(json.dumps(cfg))
            (root/"progress.json").write_text('{"quiet_positions":19999999}')
            with self.assertRaisesRegex(ValueError,"19,999,999"):
                campaign.load_data(Path(d))

    def test_every_gate_has_a_distinct_reserved_book(self):
        books=campaign.PINS["books"]
        self.assertEqual(set(books),set(campaign.PINS["candidates"])|set(campaign.RECIPES)|{"confirmation"})
        self.assertEqual(len(set(v["sha256"] for v in books.values())),len(books))
        self.assertEqual(len(set(v["seed"] for v in books.values())),len(books))
        self.assertTrue(all(v["pairs"]==2000 for v in books.values()))
        self.assertEqual(sha(SUITE),SUITE_HASH)

    def test_opening_moves_must_reach_recorded_position(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"book.epd"
            fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -"
            moves="b1c3 b8c6 c3b1 c6b8 b1c3 b8c6 c3b1 c6b8".split()
            p.write_text(fen+"\n")
            m=dict(format="fresh-8ply-v1",pairs=1,seed=1,sha256=sha(p),openings=[[fen,moves,0]])
            p.with_suffix(".json").write_text(json.dumps(m))
            self.assertEqual(verify(p,replay=True)["pairs"],1)
            moves[-1]="g8f6"
            p.with_suffix(".json").write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,"replay"):
                verify(p,replay=True)

    def test_failed_qualification_is_not_an_elo_result(self):
        from subprocess import CalledProcessError
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for name in campaign.RECIPES:
                work=root/("campaign-"+name)
                work.mkdir()
                (work/"queen.json").write_text('{"passed":false}')
            failure=CalledProcessError(3,["python","-m","training.qualify_standalone"])
            with patch.object(campaign,"fit",side_effect=failure) as fit, patch.object(campaign,"match") as match:
                self.assertFalse(campaign.networks(root))
                self.assertEqual(fit.call_count,2)
                match.assert_not_called()
            with patch.object(campaign,"fit",side_effect=CalledProcessError(1,["trainer"])):
                with self.assertRaises(CalledProcessError):
                    campaign.networks(root)
