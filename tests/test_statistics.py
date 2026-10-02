import unittest

from chess_ai.statistics import paired_interval
from chess_ai.backtest import OPENINGS, opening_board


class StatisticsTests(unittest.TestCase):
    def test_draws_do_not_produce_zero_uncertainty(self):
        result = paired_interval([0.5] * 20)
        self.assertLess(result["score_low"], 0.5)
        self.assertGreater(result["score_high"], 0.5)
        self.assertEqual(result["pairs"], 10)

    def test_more_pairs_narrow_the_interval(self):
        small = paired_interval([1, 0] * 4)
        large = paired_interval([1, 0] * 40)
        self.assertGreater(large["score_low"], small["score_low"])

    def test_extreme_results_remain_uncertain(self):
        self.assertLess(paired_interval([1, 1])["score_low"], 0.5)

    def test_incomplete_pairs_are_rejected(self):
        with self.assertRaises(ValueError):
            paired_interval([1, 0, 1])

    def test_every_opening_is_legal_and_distinct(self):
        positions = {opening_board(moves).to_fen() for _, moves in OPENINGS}
        self.assertEqual(len(positions), len(OPENINGS))
