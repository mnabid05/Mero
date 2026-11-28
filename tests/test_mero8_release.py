"""Check that the shipped checkpoint and public match ledger refer to the same release."""
import hashlib
import gzip
import json
from pathlib import Path
import re
import unittest
from collections import Counter


ROOT = Path(__file__).resolve().parents[1]


class Mero8ReleaseTests(unittest.TestCase):
    def test_two_independent_wins_for_the_bundled_network(self):
        evidence = json.loads((ROOT / "backtests/mero-8-release.json").read_text())
        weights = (ROOT / "training/checkpoints/mero-8.bin").read_bytes()
        qualified = evidence["training"]["parity"]
        self.assertEqual(hashlib.sha256(weights).hexdigest(), qualified["weights_sha256"])
        self.assertEqual(qualified["integer_mismatches"], 0)
        trials = evidence["trials"]
        self.assertEqual([x["name"] for x in trials], ["primary", "confirmation"])
        self.assertEqual(len({t["audit"]["sha256"]["book"] for t in trials}), 2)
        self.assertEqual(len({t["audit"]["sha256"]["baseline"] for t in trials}), 1)
        for trial in trials:
            with self.subTest(book=trial["name"]):
                audit, result = trial["audit"], trial["result"]
                self.assertEqual(audit["sha256"]["candidate"], qualified["binary_sha256"])
                pairs = trial["candidate_result_by_pair_white_then_black"].split()
                archive = ROOT / "backtests" / f"mero-8-{trial['name']}.log.gz"
                book = archive.with_suffix("").with_suffix(".epd.gz")
                positions = gzip.decompress(book.read_bytes())
                self.assertEqual(hashlib.sha256(positions).hexdigest(), audit["sha256"]["book"])
                self.assertEqual(len(positions.splitlines()), 2000)
                log = gzip.decompress(archive.read_bytes())
                self.assertEqual(hashlib.sha256(log).hexdigest(), audit["log_sha256"])
                observed = {}
                for n, white, black, outcome in re.findall(
                    r"^Finished game (\d+) \((New|Main) vs (New|Main)\): (1-0|0-1|1/2-1/2) ", log.decode(), re.M
                ):
                    i = int(n)
                    self.assertNotIn(i, observed)
                    self.assertEqual((white, black), ("New", "Main") if i % 2 else ("Main", "New"))
                    score = {"1-0": 2, "1/2-1/2": 1, "0-1": 0}[outcome]
                    observed[i] = "LDW"[score if white == "New" else 2 - score]
                self.assertEqual("".join(observed[i] for i in range(1, len(observed) + 1)), "".join(pairs))
                self.assertTrue(all(len(p) == 2 for p in pairs))
                bins = Counter(sum("LDW".index(r) for r in p) for p in pairs)
                self.assertEqual([bins[i] for i in range(5)], audit["pentanomial"])
                self.assertEqual(2 * len(pairs), result["games"])
                counts = Counter("".join(pairs))
                self.assertEqual([counts[r] for r in "WDL"],
                                 [result[k] for k in ("wins", "draws", "losses")])
                self.assertEqual(result["faults"], [])
                self.assertEqual(result["status"], "H1")
                self.assertGreater(result["reported_llr"], 2.94)
