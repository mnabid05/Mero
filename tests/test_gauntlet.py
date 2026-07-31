import unittest

from chess_ai.gauntlet import estimate_rating


class RatingEstimateTests(unittest.TestCase):
    def test_even_score_matches_opponent_rating(self):
        estimate = estimate_rating([(1500, 1.0), (1500, 0.0)])
        self.assertEqual(estimate.elo, 1500)
        self.assertLess(estimate.confidence_low, estimate.elo)
        self.assertGreater(estimate.confidence_high, estimate.elo)

    def test_better_results_raise_estimate(self):
        estimate = estimate_rating(
            [(1500, 1.0), (1500, 1.0), (1500, 0.5), (1500, 0.0)]
        )
        self.assertGreater(estimate.elo, 1500)

    def test_empty_results_are_rejected(self):
        with self.assertRaises(ValueError):
            estimate_rating([])


if __name__ == "__main__":
    unittest.main()
