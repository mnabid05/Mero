import copy
import unittest

from chess_ai.board import Board
from scripts.verify_match import verify_report


class ReplayTests(unittest.TestCase):
    def report(self):
        board = Board.starting()
        board.play_uci("e2e4")
        return {"wins": 0, "draws": 1, "losses": 0, "score_percent": 50.0,
                "records": [{"moves": ["e2e4"], "final_fen": board.to_fen(),
                             "plies": 1, "candidate_color": "white",
                             "candidate_score": 0.5, "reason": "maximum plies"}]}

    def test_valid_report_replays(self):
        self.assertEqual(verify_report(self.report()), 1)

    def test_corrupt_reports_fail(self):
        original = self.report()
        for field, value in (("final_fen", Board.starting().to_fen()),
                             ("candidate_score", 1), ("plies", 2),
                             ("reason", "threefold repetition")):
            with self.subTest(field=field):
                report = copy.deepcopy(original)
                report["records"][0][field] = value
                with self.assertRaises(ValueError):
                    verify_report(report)

    def test_false_totals_fail(self):
        report = self.report()
        report["wins"] = 1
        with self.assertRaises(ValueError):
            verify_report(report)
