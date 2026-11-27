import csv
import tempfile
import unittest
from pathlib import Path
from training import opening_holdout as h


class OpeningHoldout(unittest.TestCase):
    # Same legal position through distinct orders. Only the second spelling
    # creates a nominal (uncapturable) en-passant target on the last move.
    one=tuple("g1f3 g8f6 b1c3 b8c6 d2d4 d7d5 e2e3 e7e6".split())
    two=tuple("e2e3 e7e6 b1c3 b8c6 g1f3 g8f6 d2d4 d7d5".split())

    def test_game_partition_is_a_position_property(self):
        k=h.opening_key(self.one)
        self.assertEqual(k,h.opening_key(self.two))
        with tempfile.TemporaryDirectory() as d:
            shard=Path(d)
            with (shard/"games.tsv").open("w",newline="") as fp:
                writer=csv.DictWriter(fp,["uci_moves","rows"],delimiter="\t")
                writer.writeheader()
                for moves,n in ((self.one,14),(self.two,11),(("f2f3",),0)):
                    writer.writerow(dict(uci_moves=" ".join(moves),rows=n))
            excluded,meta=h.partition([shard],{k:"net256"},1701)
            self.assertEqual(excluded,[bytes([h.RESERVED,h.RESERVED,h.SHORT])])
            self.assertEqual(meta["excluded_games"],{"net256":2})
            self.assertEqual(meta["excluded_records"],{"net256":25})
            ordinary,_=h.partition([shard],{},1701)
            self.assertEqual(ordinary[0][0],ordinary[0][1])
            self.assertIn(ordinary[0][0],(h.TRAIN,h.VALID))

    def test_early_terminal_may_not_supply_training_rows(self):
        with tempfile.TemporaryDirectory() as d:
            shard=Path(d)
            (shard/"games.tsv").write_text("uci_moves\trows\nf2f3 e7e5 g2g4 d8h4\t1\n")
            with self.assertRaisesRegex(ValueError,"before the opening"):
                h.partition([shard],{},1701)
