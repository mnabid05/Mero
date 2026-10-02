import unittest

from chess_ai.match import run_match, score_to_elo
from chess_ai.backtest import repetition_key
from chess_ai.board import Board


class MatchHarnessTests(unittest.TestCase):
    def test_repetition_ignores_illegal_en_passant_capture(self):
        with_ep = Board.from_fen("8/6bb/8/8/R1pP2k1/4P3/P7/K7 b - d3 0 1")
        without_ep = Board.from_fen("8/6bb/8/8/R1pP2k1/4P3/P7/K7 b - - 0 1")
        self.assertEqual(repetition_key(with_ep), repetition_key(without_ep))

    def test_zero_length_matches_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "max plies"):
            run_match(("candidate",), ("baseline",), 2, 20, 0)

    def test_score_to_elo_is_symmetric(self):
        self.assertEqual(score_to_elo(0.5), 0)
        self.assertEqual(score_to_elo(0.64), -score_to_elo(0.36))
        self.assertGreaterEqual(score_to_elo(0.64), 99)

    def test_matches_require_paired_games(self):
        with self.assertRaisesRegex(ValueError, "positive even"):
            run_match(("candidate",), ("baseline",), 3, 20, 80)

    def test_matches_validate_search_resources(self):
        with self.assertRaisesRegex(ValueError, "at least 10"):
            run_match(("candidate",), ("baseline",), 2, 5, 80)
        with self.assertRaisesRegex(ValueError, "between 1 and 64"):
            run_match(
                ("candidate",),
                ("baseline",),
                2,
                20,
                80,
                candidate_threads=0,
            )
        with self.assertRaisesRegex(ValueError, "between 1 and 64"):
            run_match(
                ("candidate",),
                ("baseline",),
                2,
                20,
                80,
                baseline_threads=65,
            )


if __name__ == "__main__":
    unittest.main()
