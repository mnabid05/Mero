import unittest
from scripts.sprt_status import summarize

class SprtStatusTests(unittest.TestCase):
    games = ["Finished game 1 (New vs Main): 1-0 {White mates}",
             "Finished game 2 (Main vs New): 1-0 {White mates}"]
    def trial(self, llr, rounds=2000):
        return summarize(self.games + [f"LLR: {llr} (99.9%) (-2.94, 2.94) [0.00, 10.00]",
                         "SPRT ([0.00, 10.00]) completed - H1 was accepted", "Finished match"],
                         rounds=rounds)

    def test_cap_does_not_masquerade_as_a_pass(self):
        self.assertEqual(self.trial(0.15, 1)["status"], "inconclusive")
        self.assertEqual(self.trial(2.94, 1)["status"], "inconclusive")
        self.assertEqual(self.trial(2.97)["status"], "H1")

    def test_live_score_counts_colors_without_promoting(self):
        report = summarize(self.games)
        self.assertEqual((report["wins"], report["losses"], report["status"]), (1,1,"running"))

    def test_engine_fault_supersedes_reported_pass(self):
        lines = [self.games[0].replace("White mates","Black loses on time"),
                 "LLR: 3.00 (100%) (-2.94, 2.94) [0.00, 10.00]",
                 "SPRT ([0.00, 10.00]) completed - H1 was accepted", "Finished match"]
        self.assertEqual(summarize(lines)["status"], "invalid: engine fault")
